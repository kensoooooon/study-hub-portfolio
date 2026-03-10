from django.urls import path


from line_channels.views import (
    LineChannelListView, LineChannelDetailView,
    LineChannelActivateConfirmView, LineChannelActivateView,
    LineChannelDeactivateConfirmView, LineChannelDeactivateView,
    ChannelSecretRotateView, ChannelAccessTokenRotateView
)


app_name = "line_channels"
urlpatterns = [
    path('list/', LineChannelListView.as_view(), name="list"),
    path('detail/<int:pk>/', LineChannelDetailView.as_view(), name="detail"),
    path('activate_confirm/<int:pk>/', LineChannelActivateConfirmView.as_view(), name="activate_confirm"),
    path('activate/<int:pk>/', LineChannelActivateView.as_view(), name="activate"),
    path('deactivate_confirm/<int:pk>/', LineChannelDeactivateConfirmView.as_view(), name="deactivate_confirm"),
    path('deactivate/<int:pk>/', LineChannelDeactivateView.as_view(), name="deactivate"),
    path('rotate_channel_secret/<int:pk>/', ChannelSecretRotateView.as_view(), name="rotate_channel_secret"),
    path('rotate_channel_access_token/<int:pk>/', ChannelAccessTokenRotateView.as_view(), name="rotate_channel_access_token"),
]
