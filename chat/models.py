from django.db import models
from django.contrib.auth.models import User



class Chat(models.Model):
    participants = models.ManyToManyField(User)
    time_started = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return "Chat between users"

    def get_latest_messages(self, timestamp):
        return self.messages.filter(
            timestamp__gt=timestamp
        )


class Message(models.Model):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, null=True, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_messages")
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return self.content
