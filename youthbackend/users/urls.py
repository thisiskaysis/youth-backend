from django.urls import path

from . import views

urlpatterns = [
    path('', views.UserList.as_view(), name='user-list'),
    path('me/', views.CurrentUser.as_view(), name='user-me'),
    path('search/', views.PeopleSearch.as_view(), name='people-search'),
    path('visitors/', views.VisitorCreate.as_view(), name='visitor-create'),
    path('<int:pk>/', views.UserDetail.as_view(), name='user-detail'),
]
