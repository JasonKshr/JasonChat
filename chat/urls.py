from django.urls import path
from . import views

urlpatterns = [
    path("", views.list_conversations),
    path("create/", views.create_conversation),
    path("send/", views.send_message),
    path("<int:conversation_id>/messages/", views.get_messages),
    path("messages/<int:message_id>/edit/", views.edit_message),
    path("messages/<int:message_id>/delete/", views.delete_message),
    path("<int:conversation_id>/add-participant/", views.add_participant),
    path("<int:conversation_id>/remove-participant/", views.remove_participant),
    path("<int:conversation_id>/promote-admin/", views.promote_admin),
    path("<int:conversation_id>/demote-admin/", views.demote_admin),
    path("<int:conversation_id>/participants/", views.list_participants),
    path("<int:conversation_id>/rename/", views.rename_group),
    path("<int:conversation_id>/delete/", views.delete_group),
]