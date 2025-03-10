from django.contrib import admin
from .models import Message, Chat


class MessageAdmin(admin.ModelAdmin):
    list_display = ['sender', 'receiver', 'timestamp']
admin.site.register(Message, MessageAdmin)



class ChatAdmin(admin.ModelAdmin):
    list_display = ['time_started',]
admin.site.register(Chat, ChatAdmin)

