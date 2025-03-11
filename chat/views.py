# Standard library imports
import time

# Django imports
from django.shortcuts import render, redirect
from django.http import JsonResponse, StreamingHttpResponse
from django.contrib.auth import get_user_model, authenticate, login, logout
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth.decorators import login_required

# Django REST Framework imports
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from rest_framework.views import APIView

# Local imports
from .models import Message, Chat
from .serializers import MessageSerializer, UserSerializer, ChatListSerializer

# Constants
User = get_user_model()


def signup_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if User.objects.filter(username=username).exists():
            return render(request, 'accounts/signup.html', {'error': 'Username already exists'})
        
        user = User.objects.create_user(username=username, password=password)
        
        login(request, user)
        return redirect('index')  
    return render(request, 'accounts/signup.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('index') 
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'accounts/login.html')



def logout_view(request):
    if request.method == 'POST':
        logout(request)
        return redirect('login')  
    else:
        return redirect('index')



@login_required
def index(request):
    chat_list = get_chat_list(request.user)
    return render(request, "chats/index.html", {"chat_list": chat_list})



class UserListAPIView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return User.objects.exclude(id=self.request.user.id)

    def list(self, request, *args, **kwargs):
        # return JSON to external consumer (mobile App) and html to web
        accept_header = request.headers.get('Accept', '')
        queryset = self.get_queryset()

        if 'application/json' in accept_header:
            serializer = self.get_serializer(queryset, many=True)
            return JsonResponse({"users": serializer.data}, safe=False)
        return render(request, "chats/user_list.html", {"user_list": queryset})



class ChatListAPIView(generics.ListAPIView):
    serializer_class = ChatListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request, *args, **kwargs):
        # return JSON to external consumer (mobile App) and html to web
        accept_header = request.headers.get('Accept', '')
        chat_list = get_chat_list(request.user)
        serializer = ChatListSerializer(chat_list, many=True)

        if 'application/json' in accept_header:
            return Response({"chat_list": serializer.data})
        
        return render(request, "chats/chat_list.html", {"chat_list": chat_list})



class UserSearchAPIView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = User.objects.exclude(id=self.request.user.id)
        search_query = self.request.GET.get('user_search', '').strip()
        
        if search_query:
            queryset = queryset.filter(
                Q(username__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query)
            )
        return queryset

    def list(self, request, *args, **kwargs):
        # return JSON to external consumer (mobile App) and html to web
        accept_header = request.headers.get('Accept', '')
        queryset = self.get_queryset()

        if 'application/json' in accept_header:
            serializer = self.get_serializer(queryset, many=True)
            return JsonResponse({"users": serializer.data}, safe=False)
        
        return render(request, "partials/user_search.html", {"user_list": queryset})



class ConversationAPIView(generics.ListAPIView):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    other_user = None 

    def get_queryset(self):
        other_user_id = self.kwargs["user_id"]        
        try:
            self.other_user = User.objects.get(id=other_user_id)
        except User.DoesNotExist:
            raise NotFound(detail="The user you are trying to chat with does not exist.")

        messages = Message.objects.filter(
            sender__in=[self.request.user, self.other_user],
            receiver__in=[self.request.user, self.other_user]
        ).order_by("timestamp")

        return messages

    def list(self, request, *args, **kwargs):
        # return JSON to external consumer (mobile App) and html to web
        accept_header = request.headers.get('Accept', '')
        queryset = self.get_queryset()

        if 'application/json' in accept_header:
            serializer = self.get_serializer(queryset, many=True)
            return JsonResponse(serializer.data, safe=False)

        context = {
            "messages": queryset, 
            "other_user": self.other_user
        }
        return render(request, "chats/conversation.html", context)



class SendMessageAPIView(generics.CreateAPIView):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    message = None
    
    def perform_create(self, serializer):
        other_user_id = self.kwargs["user_id"]
        try:
            receiver = User.objects.get(id=other_user_id)
        except User.DoesNotExist:
            raise NotFound(detail="The user you are trying to chat with does not exist.")

     
        chat = Chat.objects.filter(participants=self.request.user).filter(participants=receiver).first()
     
        if not chat:
            chat = Chat.objects.create()
            chat.participants.set([self.request.user, receiver])
                
        if self.request.content_type == 'application/json':
            message_content = self.request.data.get('content')
        else:
            message_content = self.request.POST.get('content')
        self.message = serializer.save(sender=self.request.user, receiver=receiver, content=message_content, chat=chat)


    def create(self, request, *args, **kwargs):
        # return JSON to external consumer (mobile App) and html to web
        accept_header = request.headers.get('Accept', '')
        response = super().create(request, *args, **kwargs)

        if 'application/json' in accept_header:
            return response
        return render(request, "partials/message_fragment.html", {"message": self.message})



def message_stream(request, user_id):
    def event_stream():
        last_timestamp = timezone.now()
        timeout = 240  
        last_activity = timezone.now()

        while True:
            new_messages = Message.objects.filter(
                sender__in=[request.user, user_id],
                receiver__in=[request.user, user_id],
                timestamp__gt=last_timestamp
            ).order_by("timestamp")

            if new_messages:
                last_timestamp = new_messages[len(new_messages) - 1].timestamp
                
                received_messages = new_messages.filter(
                    sender=user_id,
                    receiver=request.user
                )

                for latest_message in received_messages:
                    formatted_time = latest_message.timestamp.strftime("%B %d, %Y, %I:%M %p").replace(" 0", " ").lower().replace("am", "a.m.").replace("pm", "p.m.")
                    html_message = (
                        f'<div class="message received">'
                        f'<div class="content">'
                        f'<div class="text">{latest_message.content}</div>'
                        f'<div class="timestamp">{formatted_time}</div>'
                        f'</div>'
                        f'</div>'
                    )
                    yield f"event: message\ndata: {html_message}\n\n"


                # Update last activity time
                last_activity = timezone.now()
            else:
                if (timezone.now() - last_activity).total_seconds() > timeout:

                    close_message = (
                        f'<div class="text-danger" style="text-align: center;">'
                        f'<div class="text">Connection closed due to inactivity, Refresh the page to continue</div>'
                        f'</div>'
                    )
        
                    yield f"event: close\ndata: {close_message}\n\n"
                    break
            
            time.sleep(2)

    response_server = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response_server['Cache-Control'] = 'no-cache'  
    response_server["X-Accel-Buffering"] = "no" 
    response_server["Connection"] = "keep-alive" 
    return response_server



def get_chat_list(user):
    chats = Chat.objects.filter(participants=user).prefetch_related("participants", "messages")
    chat_list = []
    
    for chat in chats:
        latest_message = chat.messages.order_by('-timestamp').first()  
        other_user = chat.participants.exclude(id=user.id).first() 
        chat_list.append({
            'latest_message': latest_message,
            'latest_message_timestamp': latest_message.timestamp,
            'other_user': other_user
        })

    chat_list.sort(key=lambda x: x['latest_message_timestamp'], reverse=True)

    return chat_list
