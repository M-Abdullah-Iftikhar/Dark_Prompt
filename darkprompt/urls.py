"""Project URL configuration for Dark Prompt."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include(("core.urls", "core"), namespace="core")),
    path("", include(("accounts.urls", "accounts"), namespace="accounts")),
    path("", include(("chat.urls", "chat"), namespace="chat")),
]

# Register the project-wide 404 handler. Django uses this only when
# DEBUG=False; while DEBUG=True it shows the yellow technical page instead.
# Use /404-preview/ during development to inspect the styled template.
handler404 = "core.views.not_found_view"
handler500 = "core.views.server_error_view"
