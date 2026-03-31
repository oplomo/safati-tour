import json
from functools import wraps
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen
from datetime import date

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, F, Min, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from .forms import BlogCommentForm, BookingRequestForm, ContactForm, LoginForm, RegisterForm
from .models import (
    BlogComment,
    BlogCommentReaction,
    BlogPost,
    BlogPostReaction,
    BlogPostShare,
    BlogPostView,
    Category,
    Destination,
    Inquiry,
    Tour,
    TourDate,
    User,
)


def _dashboard_sections(active_key=None):
    sections = [
        {'key': 'overview', 'label': 'Overview', 'route': 'safarisite:dashboard_home', 'summary': 'Main admin control room'},
        {'key': 'tours', 'label': 'Tours', 'route': 'safarisite:dashboard_tours', 'summary': 'Trips, dates, and pricing'},
        {'key': 'destinations', 'label': 'Destinations', 'route': 'safarisite:dashboard_destinations', 'summary': 'Places and regional content'},
        {'key': 'bookings', 'label': 'Bookings', 'route': 'safarisite:dashboard_bookings', 'summary': 'Booking requests and follow-up'},
        {'key': 'blogs', 'label': 'Blogs', 'route': 'safarisite:dashboard_blogs', 'summary': 'Stories, posts, and publishing'},
        {'key': 'inquiries', 'label': 'Inquiries', 'route': 'safarisite:dashboard_inquiries', 'summary': 'Messages and support requests'},
        {'key': 'users', 'label': 'Users', 'route': 'safarisite:dashboard_users', 'summary': 'Travelers, staff, and admins'},
        {'key': 'comments', 'label': 'Comments', 'route': 'safarisite:dashboard_comments', 'summary': 'Community moderation area'},
        {'key': 'settings', 'label': 'Settings', 'route': 'safarisite:dashboard_settings', 'summary': 'Site-wide configuration'},
    ]

    for section in sections:
        section['is_active'] = section['key'] == active_key

    return sections


def _dashboard_base_context(active_key):
    recent_bookings = Inquiry.objects.filter(inquiry_type='booking').select_related('tour').order_by('-created_at')[:5]
    recent_inquiries = Inquiry.objects.exclude(inquiry_type='booking').order_by('-created_at')[:5]
    recent_posts = BlogPost.objects.order_by('-created_at')[:4]

    return {
        'dashboard_sections': _dashboard_sections(active_key),
        'dashboard_counts': {
            'tours': Tour.objects.count(),
            'destinations': Destination.objects.count(),
            'bookings': Inquiry.objects.filter(inquiry_type='booking').count(),
            'inquiries': Inquiry.objects.exclude(inquiry_type='booking').count(),
            'blogs': BlogPost.objects.count(),
            'users': User.objects.count(),
            'comments': BlogComment.objects.count(),
        },
        'recent_bookings': recent_bookings,
        'recent_inquiries': recent_inquiries,
        'recent_posts': recent_posts,
    }


def dashboard_access_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('safarisite:login')}?next={request.path}")

        allowed_roles = {'admin', 'operator'}
        if request.user.is_staff or getattr(request.user, 'user_type', '') in allowed_roles:
            return view_func(request, *args, **kwargs)

        messages.error(request, 'You do not have access to the dashboard.')
        return redirect('safarisite:home')

    return wrapped


def _auth_page_context(next_url):
    return {
        'next_url': next_url,
        'google_auth_enabled': settings.GOOGLE_OAUTH_ENABLED,
        'google_auth_client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
    }


BOOKING_CHECKOUT_SESSION_KEY = 'booking_checkout_data'


def _build_unique_username(seed_value):
    base_username = slugify(seed_value).replace('-', '')[:24] or 'traveler'
    username = base_username
    suffix = 1

    while User.objects.filter(username=username).exists():
        username = f"{base_username[:20]}{suffix}"
        suffix += 1

    return username


def _verify_google_credential(credential):
    query = urlencode({'id_token': credential})
    verify_url = f"https://oauth2.googleapis.com/tokeninfo?{query}"

    try:
        with urlopen(verify_url, timeout=10) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except (HTTPError, URLError, TimeoutError, ValueError):
        return None

    if payload.get('aud') != settings.GOOGLE_OAUTH_CLIENT_ID:
        return None

    if payload.get('email_verified') not in ('true', True):
        return None

    return payload


def _serialize_booking_data(cleaned_data):
    return {
        'name': cleaned_data['name'],
        'email': cleaned_data['email'],
        'phone': cleaned_data['phone'],
        'tour_id': cleaned_data['tour'].id,
        'preferred_date': cleaned_data['preferred_date'].isoformat() if cleaned_data['preferred_date'] else '',
        'number_of_people': cleaned_data['number_of_people'],
        'message': cleaned_data['message'],
    }


def _load_checkout_booking_data(request):
    booking_data = request.session.get(BOOKING_CHECKOUT_SESSION_KEY)
    if not booking_data:
        return None

    tour = Tour.objects.filter(id=booking_data.get('tour_id'), is_active=True).first()
    if not tour:
        return None

    preferred_date = booking_data.get('preferred_date')
    parsed_preferred_date = date.fromisoformat(preferred_date) if preferred_date else None
    traveler_count = int(booking_data.get('number_of_people') or 1)
    subtotal = tour.final_price * traveler_count

    return {
        'name': booking_data.get('name', ''),
        'email': booking_data.get('email', ''),
        'phone': booking_data.get('phone', ''),
        'tour': tour,
        'preferred_date': parsed_preferred_date,
        'number_of_people': traveler_count,
        'message': booking_data.get('message', ''),
        'subtotal': subtotal,
    }


def home(request):
    tours_qs = Tour.objects.filter(is_active=True).select_related(
        'destination',
    ).prefetch_related(
        'categories',
        'tags',
        'tour_dates',
    ).annotate(
        upcoming_departure=Min('tour_dates__start_date'),
    ).order_by('-is_featured', '-is_trending', 'price_per_person')

    destinations_qs = Destination.objects.filter(is_active=True).prefetch_related(
        'tours',
        'blog_posts',
    ).order_by('-is_featured', 'name')

    stories_qs = BlogPost.objects.filter(is_published=True).select_related(
        'destination',
        'author',
    ).annotate(
        share_total=Count('shares', distinct=True),
        comment_total=Count('comments', distinct=True),
        reaction_total=Count('reactions', distinct=True),
    ).order_by('-is_featured', '-published_at', '-created_at')

    featured_tours = tours_qs[:3]
    featured_destinations = destinations_qs[:4]
    featured_stories = stories_qs[:3]
    active_departures = TourDate.objects.filter(
        is_active=True,
        available_spots__gt=0,
        tour__is_active=True,
    ).select_related('tour', 'tour__destination').order_by('start_date')[:4]

    return render(
        request,
        'safarisite/home.html',
        {
            'featured_tours': featured_tours,
            'featured_destinations': featured_destinations,
            'featured_stories': featured_stories,
            'active_departures': active_departures,
            'tour_count': tours_qs.count(),
            'destination_count': destinations_qs.count(),
            'story_count': stories_qs.count(),
            'departure_count': TourDate.objects.filter(
                is_active=True,
                available_spots__gt=0,
                tour__is_active=True,
            ).count(),
        },
    )


@dashboard_access_required
def dashboard_home(request):
    return render(
        request,
        'safarisite/dashboard/home.html',
        _dashboard_base_context('overview') | {
            'featured_departures': TourDate.objects.filter(
                is_active=True,
                available_spots__gt=0,
            ).select_related('tour', 'tour__destination').order_by('start_date')[:6],
            'page_title': 'Admin Overview',
            'page_subtitle': 'A separate control surface for managing the platform, with a different visual identity from the public site.',
        },
    )


def _dashboard_section_page(request, active_key, title, subtitle, checklist):
    return render(
        request,
        'safarisite/dashboard/section.html',
        _dashboard_base_context(active_key) | {
            'page_title': title,
            'page_subtitle': subtitle,
            'section_checklist': checklist,
        },
    )


@dashboard_access_required
def dashboard_tours(request):
    return _dashboard_section_page(
        request,
        'tours',
        'Tour Management',
        'This page is the future workspace for adding, editing, scheduling, and publishing tours.',
        [
            'Create and edit tours',
            'Manage dates, pricing, and featured status',
            'Control categories, tags, and availability',
        ],
    )


@dashboard_access_required
def dashboard_destinations(request):
    return _dashboard_section_page(
        request,
        'destinations',
        'Destination Management',
        'This page is the future workspace for destination records, imagery, and regional content structure.',
        [
            'Add and edit destinations',
            'Manage feature flags and destination media',
            'Tie destinations into tours and blog content',
        ],
    )


@dashboard_access_required
def dashboard_bookings(request):
    return _dashboard_section_page(
        request,
        'bookings',
        'Booking Desk',
        'This page is the future workspace for reviewing booking requests and following up on travel leads.',
        [
            'Review booking requests',
            'Track preferred dates and group sizes',
            'Move leads toward confirmation',
        ],
    )


@dashboard_access_required
def dashboard_blogs(request):
    return _dashboard_section_page(
        request,
        'blogs',
        'Blog Studio',
        'This page is the future workspace for blog authoring, editing, publishing, and post management.',
        [
            'Create and update stories',
            'Control published status and featured posts',
            'Manage editorial content across destinations',
        ],
    )


@dashboard_access_required
def dashboard_inquiries(request):
    return _dashboard_section_page(
        request,
        'inquiries',
        'Inquiry Center',
        'This page is the future workspace for general, custom, group, and corporate inquiries.',
        [
            'Review messages from the site',
            'Track read and reply status',
            'Organize support and planning requests',
        ],
    )


@dashboard_access_required
def dashboard_users(request):
    return _dashboard_section_page(
        request,
        'users',
        'User Management',
        'This page is the future workspace for travelers, operators, guides, and admin accounts.',
        [
            'Review user profiles and roles',
            'Track account growth and access levels',
            'Manage operational users separately from travelers',
        ],
    )


@dashboard_access_required
def dashboard_comments(request):
    return _dashboard_section_page(
        request,
        'comments',
        'Comment Moderation',
        'This page is the future workspace for managing blog comments, replies, and reaction activity.',
        [
            'Moderate comments and replies',
            'Track community engagement',
            'Handle removals and moderation actions',
        ],
    )


@dashboard_access_required
def dashboard_settings(request):
    return _dashboard_section_page(
        request,
        'settings',
        'Platform Settings',
        'This page is the future workspace for global site settings, contact details, and platform-level preferences.',
        [
            'Manage global site information',
            'Update operational contact details',
            'Control future platform preferences',
        ],
    )


def login_view(request):
    if request.user.is_authenticated:
        return redirect('safarisite:home')

    next_url = request.GET.get('next') or request.POST.get('next') or reverse('safarisite:home')
    form = LoginForm(request, data=request.POST or None)

    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        messages.success(request, f"Welcome back, {form.get_user().username}.")
        return redirect(next_url)

    return render(
        request,
        'safarisite/auth/login.html',
        _auth_page_context(next_url) | {
            'form': form,
        },
    )


def register_view(request):
    if request.user.is_authenticated:
        return redirect('safarisite:home')

    next_url = request.GET.get('next') or request.POST.get('next') or reverse('safarisite:home')
    form = RegisterForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"Your account has been created, {user.username}.")
        return redirect(next_url)

    return render(
        request,
        'safarisite/auth/register.html',
        _auth_page_context(next_url) | {
            'form': form,
        },
    )


@require_POST
def google_auth_view(request):
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (TypeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid request payload.'}, status=400)

    credential = payload.get('credential')
    next_url = payload.get('next_url') or reverse('safarisite:home')

    if not settings.GOOGLE_OAUTH_ENABLED:
        return JsonResponse({'ok': False, 'error': 'Google sign-in is not configured.'}, status=400)

    if not credential:
        return JsonResponse({'ok': False, 'error': 'Missing Google credential.'}, status=400)

    google_payload = _verify_google_credential(credential)
    if not google_payload:
        return JsonResponse({'ok': False, 'error': 'Google sign-in could not be verified.'}, status=400)

    email = google_payload.get('email')
    given_name = google_payload.get('given_name', '')
    family_name = google_payload.get('family_name', '')
    full_name = google_payload.get('name', '')

    user = User.objects.filter(email__iexact=email).first()
    if not user:
        username_seed = email.split('@')[0] if email else full_name
        user = User.objects.create(
            username=_build_unique_username(username_seed),
            email=email,
            first_name=given_name,
            last_name=family_name,
        )
        user.set_unusable_password()
        user.save(update_fields=['password'])
        messages.success(request, f"Your account has been created with Google, {user.username}.")
    else:
        changed_fields = []
        if given_name and user.first_name != given_name:
            user.first_name = given_name
            changed_fields.append('first_name')
        if family_name and user.last_name != family_name:
            user.last_name = family_name
            changed_fields.append('last_name')
        if not user.email and email:
            user.email = email
            changed_fields.append('email')
        if changed_fields:
            user.save(update_fields=changed_fields)
        messages.success(request, f"Welcome back, {user.username}.")

    login(request, user)
    return JsonResponse({'ok': True, 'redirect_url': next_url})


@login_required
def logout_view(request):
    logout(request)
    messages.success(request, 'You have been signed out.')
    return redirect('safarisite:home')


def about(request):
    featured_destinations = Destination.objects.filter(is_active=True).prefetch_related(
        'tours',
        'blog_posts',
    ).order_by('-is_featured', 'name')[:3]
    featured_tours = Tour.objects.filter(is_active=True).select_related(
        'destination',
    ).order_by('-is_featured', '-is_trending', 'price_per_person')[:3]
    featured_stories = BlogPost.objects.filter(is_published=True).select_related(
        'destination',
    ).order_by('-is_featured', '-published_at', '-created_at')[:2]

    return render(
        request,
        'safarisite/about.html',
        {
            'featured_destinations': featured_destinations,
            'featured_tours': featured_tours,
            'featured_stories': featured_stories,
            'tour_count': Tour.objects.filter(is_active=True).count(),
            'destination_count': Destination.objects.filter(is_active=True).count(),
            'story_count': BlogPost.objects.filter(is_published=True).count(),
        },
    )


def services(request):
    active_tours = Tour.objects.filter(is_active=True).select_related('destination').order_by(
        '-is_featured',
        '-is_trending',
        'title',
    )
    featured_tours = active_tours[:3]
    featured_destinations = Destination.objects.filter(is_active=True).order_by(
        '-is_featured',
        'name',
    )[:4]
    published_stories = BlogPost.objects.filter(is_published=True).order_by(
        '-published_at',
        '-created_at',
    )[:3]

    return render(
        request,
        'safarisite/services.html',
        {
            'featured_tours': featured_tours,
            'featured_destinations': featured_destinations,
            'published_stories': published_stories,
            'tour_count': active_tours.count(),
            'destination_count': Destination.objects.filter(is_active=True).count(),
            'story_count': BlogPost.objects.filter(is_published=True).count(),
        },
    )


def tours(request):
    tours_qs = Tour.objects.filter(is_active=True).select_related(
        'destination',
    ).prefetch_related(
        'categories',
        'tags',
        'tour_dates',
    ).annotate(
        upcoming_departure=Min('tour_dates__start_date'),
    ).order_by('-is_featured', '-is_trending', 'price_per_person')

    featured_tours = tours_qs[:3]
    all_tours = tours_qs
    active_departures = TourDate.objects.filter(
        is_active=True,
        available_spots__gt=0,
        tour__is_active=True,
    ).select_related('tour', 'tour__destination').order_by('start_date')[:6]
    destination_count = Destination.objects.filter(tours__is_active=True).distinct().count()
    category_count = Category.objects.filter(tours__is_active=True).distinct().count()

    return render(
        request,
        'safarisite/tours.html',
        {
            'featured_tours': featured_tours,
            'tours': all_tours,
            'active_departures': active_departures,
            'tour_count': all_tours.count(),
            'destination_count': destination_count,
            'category_count': category_count,
        },
    )


def destinations(request):
    destinations_qs = Destination.objects.filter(is_active=True).prefetch_related(
        'tours',
        'blog_posts',
    ).order_by('-is_featured', 'name')

    featured_destinations = destinations_qs[:3]
    all_destinations = destinations_qs
    featured_count = destinations_qs.filter(is_featured=True).count()
    country_count = destinations_qs.values('country').distinct().count()

    return render(
        request,
        'safarisite/destinations.html',
        {
            'featured_destinations': featured_destinations,
            'destinations': all_destinations,
            'destination_count': all_destinations.count(),
            'featured_count': featured_count,
            'country_count': country_count,
        },
    )


def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            Inquiry.objects.create(
                user=request.user if request.user.is_authenticated else None,
                name=form.cleaned_data['name'],
                email=form.cleaned_data['email'],
                phone=form.cleaned_data['phone'],
                inquiry_type=form.cleaned_data['inquiry_type'],
                subject=form.cleaned_data['subject'],
                message=form.cleaned_data['message'],
            )
            messages.success(request, 'Your message has been sent. We will get back to you shortly.')
            return redirect('safarisite:contact')
    else:
        form = ContactForm()

    featured_tours = Tour.objects.filter(is_active=True).select_related('destination').order_by(
        '-is_featured',
        '-is_trending',
        'title',
    )[:3]
    featured_destinations = Destination.objects.filter(is_active=True).order_by(
        '-is_featured',
        'name',
    )[:3]

    return render(
        request,
        'safarisite/contact.html',
        {
            'form': form,
            'featured_tours': featured_tours,
            'featured_destinations': featured_destinations,
            'tour_count': Tour.objects.filter(is_active=True).count(),
            'destination_count': Destination.objects.filter(is_active=True).count(),
        },
    )


def booking(request):
    if request.method == 'POST':
        form = BookingRequestForm(request.POST)
        if form.is_valid():
            request.session[BOOKING_CHECKOUT_SESSION_KEY] = _serialize_booking_data(form.cleaned_data)
            request.session.modified = True
            return redirect('safarisite:booking_checkout')
    else:
        initial = {}
        tour_slug = request.GET.get('tour')
        if tour_slug:
            from .models import Tour
            selected_tour = Tour.objects.filter(slug=tour_slug, is_active=True).first()
            if selected_tour:
                initial['tour'] = selected_tour
        form = BookingRequestForm(initial=initial)

    return render(request, 'safarisite/booking.html', {'form': form})


def booking_checkout(request):
    checkout_data = _load_checkout_booking_data(request)
    if not checkout_data:
        messages.error(request, 'Start with the booking form before continuing to checkout.')
        return redirect('safarisite:booking')

    if request.method == 'POST':
        inquiry = Inquiry.objects.create(
            user=request.user if request.user.is_authenticated else None,
            tour=checkout_data['tour'],
            name=checkout_data['name'],
            email=checkout_data['email'],
            phone=checkout_data['phone'],
            inquiry_type='booking',
            subject=f"Booking request for {checkout_data['tour'].title}",
            message=checkout_data['message'],
            preferred_date=checkout_data['preferred_date'] or None,
            number_of_people=checkout_data['number_of_people'],
        )
        request.session.pop(BOOKING_CHECKOUT_SESSION_KEY, None)
        messages.success(request, 'Payment received successfully. Your booking has been confirmed.')
        return redirect('safarisite:booking_complete', inquiry_id=inquiry.id)

    return render(
        request,
        'safarisite/booking_checkout.html',
        {
            'checkout': checkout_data,
        },
    )


def booking_complete(request, inquiry_id):
    booking = get_object_or_404(Inquiry, id=inquiry_id, inquiry_type='booking')
    return render(
        request,
        'safarisite/booking_complete.html',
        {
            'booking': booking,
        },
    )


@login_required
def my_bookings(request):
    today = date.today()
    booking_qs = Inquiry.objects.filter(
        user=request.user,
        inquiry_type='booking',
    ).select_related(
        'tour',
        'tour__destination',
    ).order_by('-preferred_date', '-created_at')

    active_trip = booking_qs.filter(preferred_date__gte=today).order_by('preferred_date', '-created_at').first()
    recent_trip = booking_qs.filter(preferred_date__lt=today).order_by('-preferred_date', '-created_at').first()

    if not recent_trip:
        recent_trip = booking_qs.exclude(id=getattr(active_trip, 'id', None)).order_by('-created_at').first()

    hero_trip = active_trip or recent_trip
    hero_mode = 'active' if active_trip else 'recent' if recent_trip else 'empty'

    booked_tour_ids = list(booking_qs.exclude(tour__isnull=True).values_list('tour_id', flat=True))
    suggestion_qs = Tour.objects.filter(is_active=True).exclude(id__in=booked_tour_ids).select_related(
        'destination',
    ).prefetch_related(
        'categories',
    ).order_by('-is_trending', '-is_featured', 'price_per_person')

    if hero_trip and hero_trip.tour:
        related_suggestions = suggestion_qs.filter(destination=hero_trip.tour.destination)[:2]
        related_ids = [tour.id for tour in related_suggestions]
        extra_suggestions = suggestion_qs.exclude(id__in=related_ids)[:3]
        next_trips = list(related_suggestions) + list(extra_suggestions)
    else:
        next_trips = list(suggestion_qs[:5])

    return render(
        request,
        'safarisite/my_bookings.html',
        {
            'active_trip': active_trip,
            'recent_trip': recent_trip,
            'hero_trip': hero_trip,
            'hero_mode': hero_mode,
            'booking_history': booking_qs[:6],
            'next_trips': next_trips[:5],
        },
    )


def blogs(request):
    blog_posts = BlogPost.objects.filter(is_published=True).select_related(
        'author',
        'destination',
    ).annotate(
        share_total=Count('shares', distinct=True),
        comment_total=Count('comments', distinct=True),
        reaction_total=Count('reactions', distinct=True),
    ).prefetch_related(
        'shares__user',
        'reactions__user',
        'comments__user',
    )

    if blog_posts.exists():
        items = blog_posts.order_by('-published_at', '-created_at')
    else:
        items = [
            {
                'title': 'Moonlit Drives Across the Mara',
                'excerpt': 'A cinematic guide to night safaris, lantern dinners, and the silence that makes every distant roar feel electric.',
                'destination': {'name': 'Masai Mara'},
                'read_time_minutes': 6,
                'published_at': date(2026, 2, 16),
                'is_featured': True,
                'share_total': 0,
                'comment_total': 0,
                'reaction_total': 0,
            },
            {
                'title': 'The Gold Hour Route Through Amboseli',
                'excerpt': 'Where to stand, when to leave camp, and how to frame elephants against the cold geometry of Kilimanjaro.',
                'destination': {'name': 'Amboseli'},
                'read_time_minutes': 5,
                'published_at': date(2026, 2, 10),
                'is_featured': True,
                'share_total': 0,
                'comment_total': 0,
                'reaction_total': 0,
            },
            {
                'title': 'Zanzibar After Safari',
                'excerpt': 'A softer second chapter built around ocean air, carved doors, spice markets, and slow coastal evenings.',
                'destination': {'name': 'Zanzibar'},
                'read_time_minutes': 4,
                'published_at': date(2026, 1, 28),
                'is_featured': False,
                'share_total': 0,
                'comment_total': 0,
                'reaction_total': 0,
            },
            {
                'title': 'Volcano Trails and Gorilla Dawn',
                'excerpt': 'A field note on rhythm, altitude, and the emotional weight of encountering mountain gorillas at first light.',
                'destination': {'name': 'Rwanda'},
                'read_time_minutes': 7,
                'published_at': date(2026, 1, 21),
                'is_featured': True,
                'share_total': 0,
                'comment_total': 0,
                'reaction_total': 0,
            },
            {
                'title': 'How to Pack for a Luxury Tent Safari',
                'excerpt': 'A practical edit of what matters, what does not, and how to pack light without looking underprepared.',
                'destination': {'name': 'Serengeti'},
                'read_time_minutes': 5,
                'published_at': date(2026, 1, 14),
                'is_featured': False,
                'share_total': 0,
                'comment_total': 0,
                'reaction_total': 0,
            },
            {
                'title': 'Three River Crossings Worth Waiting For',
                'excerpt': 'Patience, dust, camera discipline, and the exact reason some wildlife moments can never be scheduled.',
                'destination': {'name': 'Northern Tanzania'},
                'read_time_minutes': 6,
                'published_at': date(2025, 12, 30),
                'is_featured': False,
                'share_total': 0,
                'comment_total': 0,
                'reaction_total': 0,
            },
            {
                'title': 'A Design Lover’s Guide to Safari Lodges',
                'excerpt': 'Texture, light, handmade objects, and the lodge interiors that turn a stopover into part of the story.',
                'destination': {'name': 'Laikipia'},
                'read_time_minutes': 8,
                'published_at': date(2025, 12, 12),
                'is_featured': True,
                'share_total': 0,
                'comment_total': 0,
                'reaction_total': 0,
            },
            {
                'title': 'Best Season for the Great Migration',
                'excerpt': 'The short answer is not enough. This breaks down movement, weather, crowds, and photographic tradeoffs month by month.',
                'destination': {'name': 'Serengeti-Mara'},
                'read_time_minutes': 7,
                'published_at': date(2025, 11, 25),
                'is_featured': False,
                'share_total': 0,
                'comment_total': 0,
                'reaction_total': 0,
            },
            {
                'title': 'Cape Town to Kruger in One Clean Itinerary',
                'excerpt': 'A sharp city-to-bush sequence for travelers who want contrast, pace, and just enough room to breathe.',
                'destination': {'name': 'South Africa'},
                'read_time_minutes': 5,
                'published_at': date(2025, 11, 8),
                'is_featured': False,
                'share_total': 0,
                'comment_total': 0,
                'reaction_total': 0,
            },
            {
                'title': 'The Quiet Drama of Namibia',
                'excerpt': 'Why negative space, desert silence, and long horizons create one of the most visually disciplined trips in Africa.',
                'destination': {'name': 'Namibia'},
                'read_time_minutes': 6,
                'published_at': date(2025, 10, 19),
                'is_featured': True,
                'share_total': 0,
                'comment_total': 0,
                'reaction_total': 0,
            },
            {
                'title': 'Family Safaris Without the Chaos',
                'excerpt': 'How to structure travel days, age-appropriate activities, and lodge choices that keep both parents and children intact.',
                'destination': {'name': 'Kenya'},
                'read_time_minutes': 5,
                'published_at': date(2025, 10, 2),
                'is_featured': False,
                'share_total': 0,
                'comment_total': 0,
                'reaction_total': 0,
            },
            {
                'title': 'Coffee, Craters, and Cool Air in Arusha',
                'excerpt': 'The stop before the expedition deserves better writing than a transfer note. Here is the better version.',
                'destination': {'name': 'Arusha'},
                'read_time_minutes': 4,
                'published_at': date(2025, 9, 18),
                'is_featured': False,
                'share_total': 0,
                'comment_total': 0,
                'reaction_total': 0,
            },
        ]

    paginator = Paginator(items, 9)
    page_obj = paginator.get_page(request.GET.get('page'))

    if hasattr(page_obj, 'object_list'):
        for post in page_obj.object_list:
            if hasattr(post, 'shares'):
                post.share_actor_names = [
                    share.user.get_full_name() or share.user.username
                    if share.user else 'Guest visitor'
                    for share in post.shares.all()[:10]
                ]
                post.reaction_actor_names = [
                    reaction.user.get_full_name() or reaction.user.username
                    if reaction.user else 'Guest visitor'
                    for reaction in post.reactions.all()[:10]
                ]
                post.comment_actor_names = [
                    comment.display_name
                    for comment in post.comments.all()[:10]
                    if not comment.is_deleted
                ]

    return render(request, 'safarisite/blogs.html', {'page_obj': page_obj})


def _ensure_session_key(request):
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key


def _get_actor_token(request):
    session_key = _ensure_session_key(request)
    if request.user.is_authenticated:
        return f'user:{request.user.pk}'
    return f'session:{session_key}'


def _track_blog_view(request, post):
    actor_token = _get_actor_token(request)
    _, created = BlogPostView.objects.get_or_create(
        post=post,
        viewer_token=actor_token,
        defaults={
            'user': request.user if request.user.is_authenticated else None,
            'ip_address': request.META.get('REMOTE_ADDR'),
        },
    )
    if created:
        BlogPost.objects.filter(pk=post.pk).update(view_count=F('view_count') + 1)
        post.refresh_from_db(fields=['view_count'])


def _attach_comment_state(comment, actor_token):
    reaction_totals = {key: 0 for key, _ in BlogCommentReaction.REACTION_CHOICES}
    viewer_reaction = ''
    for reaction in comment.reactions.all():
        reaction_totals[reaction.reaction_type] += 1
        if reaction.actor_token == actor_token:
            viewer_reaction = reaction.reaction_type

    comment.reaction_totals = reaction_totals
    comment.viewer_reaction = viewer_reaction
    comment.can_delete = comment.owner_token == actor_token
    comment.rendered_replies = [
        _attach_comment_state(reply, actor_token)
        for reply in getattr(comment, 'prefetched_replies', [])
    ]
    return comment


def _get_reaction_totals(reactions, choices):
    totals = {key: 0 for key, _ in choices}
    for reaction in reactions:
        totals[reaction.reaction_type] += 1
    return totals


def _build_share_destination(request, post, channel):
    absolute_url = request.build_absolute_uri(reverse('safarisite:blog_detail', kwargs={'slug': post.slug}))
    title = post.title
    share_text = f"Read this safari story: {title}"
    return {
        'facebook': f"https://www.facebook.com/sharer/sharer.php?{urlencode({'u': absolute_url})}",
        'whatsapp': f"https://wa.me/?{urlencode({'text': f'{share_text} {absolute_url}'})}",
        'x': f"https://twitter.com/intent/tweet?{urlencode({'text': share_text, 'url': absolute_url})}",
        'linkedin': f"https://www.linkedin.com/sharing/share-offsite/?{urlencode({'url': absolute_url})}",
        'telegram': f"https://t.me/share/url?{urlencode({'url': absolute_url, 'text': share_text})}",
        'email': f"mailto:?{urlencode({'subject': title, 'body': f'{share_text}\\n\\n{absolute_url}'})}",
    }[channel]


def _get_comment_threads(post, actor_token):
    reaction_queryset = BlogCommentReaction.objects.order_by('created_at')
    replies_queryset = BlogComment.objects.select_related('user').prefetch_related(
        Prefetch('reactions', queryset=reaction_queryset),
    ).order_by('created_at')
    top_level_queryset = BlogComment.objects.filter(
        post=post,
        parent__isnull=True,
    ).select_related('user').prefetch_related(
        Prefetch('reactions', queryset=reaction_queryset),
        Prefetch('replies', queryset=replies_queryset, to_attr='prefetched_replies'),
    ).order_by('-created_at')
    return [_attach_comment_state(comment, actor_token) for comment in top_level_queryset]


def blog_detail(request, slug):
    post = get_object_or_404(
        BlogPost.objects.filter(is_published=True).select_related('author', 'destination'),
        slug=slug,
    )
    _track_blog_view(request, post)
    actor_token = _get_actor_token(request)
    post_reactions = list(post.reactions.all())
    post_reaction_totals = _get_reaction_totals(post_reactions, BlogPostReaction.REACTION_CHOICES)
    viewer_post_reaction = ''
    for reaction in post_reactions:
        if reaction.actor_token == actor_token:
            viewer_post_reaction = reaction.reaction_type
            break
    related_posts = BlogPost.objects.filter(
        is_published=True,
        destination=post.destination,
    ).exclude(pk=post.pk).order_by('-published_at', '-created_at')[:3]
    comments = _get_comment_threads(post, actor_token)

    return render(
        request,
        'safarisite/blog_detail.html',
        {
            'post': post,
            'related_posts': related_posts,
            'comment_form': BlogCommentForm(),
            'comments': comments,
            'comment_count': BlogComment.objects.filter(post=post, is_deleted=False).count(),
            'reaction_choices': BlogCommentReaction.REACTION_CHOICES,
            'post_reaction_choices': BlogPostReaction.REACTION_CHOICES,
            'post_reaction_totals': post_reaction_totals,
            'viewer_post_reaction': viewer_post_reaction,
            'post_reaction_count': sum(post_reaction_totals.values()),
            'share_count': BlogPostShare.objects.filter(post=post).count(),
            'share_channels': BlogPostShare.CHANNEL_CHOICES,
        },
    )


@require_POST
def react_to_post(request, slug):
    post = get_object_or_404(BlogPost.objects.filter(is_published=True), slug=slug)
    reaction_type = request.POST.get('reaction_type')
    valid_reactions = {key for key, _ in BlogPostReaction.REACTION_CHOICES}
    if reaction_type not in valid_reactions:
        return redirect('safarisite:blog_detail', slug=post.slug)

    actor_token = _get_actor_token(request)
    reaction = BlogPostReaction.objects.filter(post=post, actor_token=actor_token).first()

    if reaction and reaction.reaction_type == reaction_type:
        reaction.delete()
    else:
        BlogPostReaction.objects.update_or_create(
            post=post,
            actor_token=actor_token,
            defaults={
                'user': request.user if request.user.is_authenticated else None,
                'reaction_type': reaction_type,
            },
        )

    reaction_total = BlogPostReaction.objects.filter(post=post).count()
    actor_names = [
        reaction.user.get_full_name() or reaction.user.username if reaction.user else 'Guest visitor'
        for reaction in BlogPostReaction.objects.filter(post=post).select_related('user').order_by('-created_at')[:10]
    ]
    current_reaction = BlogPostReaction.objects.filter(post=post, actor_token=actor_token).values_list('reaction_type', flat=True).first()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'reaction_total': reaction_total,
            'actor_names': actor_names,
            'active': current_reaction == reaction_type,
        })

    next_url = request.POST.get('next')
    if next_url:
        return redirect(next_url)
    return redirect(f"{reverse('safarisite:blog_detail', kwargs={'slug': post.slug})}#post-reactions")


def share_blog_post(request, slug, channel):
    post = get_object_or_404(BlogPost.objects.filter(is_published=True), slug=slug)
    valid_channels = {key for key, _ in BlogPostShare.CHANNEL_CHOICES}
    if channel not in valid_channels:
        return redirect('safarisite:blog_detail', slug=post.slug)

    actor_token = _get_actor_token(request)
    BlogPostShare.objects.create(
        post=post,
        user=request.user if request.user.is_authenticated else None,
        actor_token=actor_token,
        channel=channel,
    )

    share_total = BlogPostShare.objects.filter(post=post).count()
    actor_names = [
        share.user.get_full_name() or share.user.username if share.user else 'Guest visitor'
        for share in BlogPostShare.objects.filter(post=post).select_related('user').order_by('-created_at')[:10]
    ]
    destination = _build_share_destination(request, post, channel)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'share_total': share_total,
            'actor_names': actor_names,
            'redirect_url': destination,
        })

    next_url = request.POST.get('next')
    if request.method == 'POST' and next_url:
        return redirect(next_url)
    return redirect(destination)


@require_POST
def add_blog_comment(request, slug):
    post = get_object_or_404(BlogPost.objects.filter(is_published=True), slug=slug)
    form = BlogCommentForm(request.POST)
    if not form.is_valid():
        return redirect(f"{reverse('safarisite:blog_detail', kwargs={'slug': post.slug})}#comments")

    actor_token = _get_actor_token(request)
    parent = None
    parent_id = request.POST.get('parent_id')
    if parent_id:
        parent = get_object_or_404(BlogComment, pk=parent_id, post=post)
        if parent.parent_id:
            parent = parent.parent

    guest_name = ''
    if not request.user.is_authenticated:
        guest_name = form.cleaned_data['guest_name'].strip()
        if not guest_name:
            return redirect(f"{reverse('safarisite:blog_detail', kwargs={'slug': post.slug})}#comments")

    BlogComment.objects.create(
        post=post,
        user=request.user if request.user.is_authenticated else None,
        guest_name=guest_name,
        owner_token=actor_token,
        parent=parent,
        content=form.cleaned_data['content'],
    )
    return redirect(f"{reverse('safarisite:blog_detail', kwargs={'slug': post.slug})}#comments")


@require_POST
def react_to_comment(request, comment_id):
    comment = get_object_or_404(BlogComment.objects.select_related('post'), pk=comment_id)
    reaction_type = request.POST.get('reaction_type')
    valid_reactions = {key for key, _ in BlogCommentReaction.REACTION_CHOICES}
    if reaction_type not in valid_reactions:
        return redirect('safarisite:blog_detail', slug=comment.post.slug)

    actor_token = _get_actor_token(request)
    reaction = BlogCommentReaction.objects.filter(comment=comment, actor_token=actor_token).first()

    if reaction and reaction.reaction_type == reaction_type:
        reaction.delete()
    else:
        BlogCommentReaction.objects.update_or_create(
            comment=comment,
            actor_token=actor_token,
            defaults={
                'user': request.user if request.user.is_authenticated else None,
                'reaction_type': reaction_type,
            },
        )

    return redirect(f"{reverse('safarisite:blog_detail', kwargs={'slug': comment.post.slug})}#comment-{comment.id}")


@require_POST
def delete_comment(request, comment_id):
    comment = get_object_or_404(BlogComment.objects.select_related('post'), pk=comment_id)
    actor_token = _get_actor_token(request)
    if comment.owner_token != actor_token:
        return redirect(f"{reverse('safarisite:blog_detail', kwargs={'slug': comment.post.slug})}#comment-{comment.id}")

    if comment.replies.exists():
        comment.is_deleted = True
        comment.content = ''
        comment.save(update_fields=['is_deleted', 'content', 'updated_at'])
    else:
        comment.delete()

    return redirect(f"{reverse('safarisite:blog_detail', kwargs={'slug': comment.post.slug})}#comments")
