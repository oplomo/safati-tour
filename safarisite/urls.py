from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = 'safarisite'

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard_home, name='dashboard_home'),
    path('dashboard/tours/', views.dashboard_tours, name='dashboard_tours'),
    path('dashboard/destinations/', views.dashboard_destinations, name='dashboard_destinations'),
    path('dashboard/bookings/', views.dashboard_bookings, name='dashboard_bookings'),
    path('dashboard/blogs/', views.dashboard_blogs, name='dashboard_blogs'),
    path('dashboard/inquiries/', views.dashboard_inquiries, name='dashboard_inquiries'),
    path('dashboard/users/', views.dashboard_users, name='dashboard_users'),
    path('dashboard/comments/', views.dashboard_comments, name='dashboard_comments'),
    path('dashboard/settings/', views.dashboard_settings, name='dashboard_settings'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('auth/google/', views.google_auth_view, name='google_auth'),
    path('logout/', views.logout_view, name='logout'),
    path('about/', views.about, name='about'),
    path('services/', views.services, name='services'),
    path('tours/', views.tours, name='tours'),
    path('destinations/', views.destinations, name='destinations'),
    path('contact/', views.contact, name='contact'),
    path('faq/', RedirectView.as_view(pattern_name='safarisite:booking', permanent=False)),
    path('booking/', views.booking, name='booking'),
    path('booking/checkout/', views.booking_checkout, name='booking_checkout'),
    path('booking/complete/<int:inquiry_id>/', views.booking_complete, name='booking_complete'),
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('blogs/', views.blogs, name='blogs'),
    path('blogs/<slug:slug>/', views.blog_detail, name='blog_detail'),
    path('blogs/<slug:slug>/react/', views.react_to_post, name='react_to_post'),
    path('blogs/<slug:slug>/share/<str:channel>/', views.share_blog_post, name='share_blog_post'),
    path('blogs/<slug:slug>/comments/add/', views.add_blog_comment, name='add_blog_comment'),
    path('blogs/comments/<int:comment_id>/react/', views.react_to_comment, name='react_to_comment'),
    path('blogs/comments/<int:comment_id>/delete/', views.delete_comment, name='delete_comment'),
]
