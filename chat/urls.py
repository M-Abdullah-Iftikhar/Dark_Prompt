from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("chat/", views.chat_page, name="chat"),
    path("api/chat/", views.api_chat, name="api_chat"),
    path("api/conversations/new/", views.api_new_conversation, name="api_new_conversation"),
    path("api/conversations/search/", views.api_search_conversations, name="api_search_conversations"),
    path("api/conversations/<int:pk>/", views.api_conversation_detail, name="api_conversation_detail"),
    path("api/conversations/<int:pk>/delete/", views.api_delete_conversation, name="api_delete_conversation"),
    path("api/conversations/<int:pk>/rename/", views.api_rename_conversation, name="api_rename_conversation"),
    path("api/conversations/<int:pk>/pin/", views.api_pin_conversation, name="api_pin_conversation"),
    path("api/conversations/<int:pk>/language/", views.api_set_conversation_language, name="api_set_conversation_language"),
    path("api/conversations/<int:pk>/export/", views.api_export_conversation, name="api_export_conversation"),
    path("api/conversations/<int:pk>/print/",  views.conversation_print_view, name="conversation_print"),
    path("api/messages/<int:pk>/regenerate/", views.api_regenerate, name="api_regenerate"),
    path("api/code/analyse/", views.api_analyse_code, name="api_analyse_code"),
    path("api/code/compile/", views.api_compile_code, name="api_compile_code"),
    path("api/builds/<slug:build_name>/<str:file_name>/", views.api_build_artefact, name="api_build_artefact"),
]
