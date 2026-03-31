from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Avg
from .models import (
    User, Destination, Category, Tag, Tour, TourDate, Guide,
    Review, Booking, Wishlist, Inquiry, BlogPost, NewsletterSubscriber,
    SiteSettings, FAQ, BlogComment, BlogCommentReaction, BlogPostView, BlogPostShare, BlogPostReaction
)

# Custom Admin Styles - Remove the BaseAdminMixin or fix it
class BaseAdminMixin:
    """Mixin to add common admin features"""
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Only annotate if these fields exist
        if hasattr(self.model, 'review') or hasattr(self.model, 'reviews'):
            try:
                return qs.annotate(
                    review_total=Count('reviews'),
                    rating_avg=Avg('reviews__overall_rating')
                )
            except:
                pass
        return qs

# Inline Classes
class TourDateInline(admin.TabularInline):
    model = TourDate
    extra = 1
    fields = ['start_date', 'end_date', 'available_spots', 'total_spots', 'is_active', 'special_price']
    classes = ['collapse']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tour')

class ReviewInline(admin.TabularInline):
    model = Review
    extra = 0
    fields = ['user', 'overall_rating', 'title', 'is_approved']
    classes = ['collapse']
    readonly_fields = ['user', 'overall_rating', 'title']
    
    def has_add_permission(self, request, obj=None):
        return False

class BookingInline(admin.TabularInline):
    model = Booking
    extra = 0
    fields = ['booking_reference', 'user', 'tour_date', 'status', 'total_price']
    classes = ['collapse']
    readonly_fields = ['booking_reference', 'user', 'tour_date', 'total_price']
    
    def has_add_permission(self, request, obj=None):
        return False

# Custom Filters
class RatingFilter(admin.SimpleListFilter):
    title = 'rating'
    parameter_name = 'rating'

    def lookups(self, request, model_admin):
        return (
            ('5', '★★★★★ (5)'),
            ('4', '★★★★☆ (4+)'),
            ('3', '★★★☆☆ (3+)'),
            ('2', '★★☆☆☆ (2+)'),
            ('1', '★☆☆☆☆ (1+)'),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(average_rating__gte=float(self.value()))
        return queryset

# Admin Classes - Fix the inheritance
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = [
        'username', 'email', 'user_type', 'get_full_name', 
        'get_review_count', 'is_active', 'date_joined_display'
    ]
    list_filter = ['user_type', 'is_active', 'is_staff', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering = ['-date_joined']
    
    fieldsets = UserAdmin.fieldsets + (
        ('Profile Information', {
            'fields': ('user_type', 'profile_image', 'bio', 'phone_number', 
                      'date_of_birth', 'preferred_currency', 'newsletter_subscription'),
            'classes': ['wide', 'collapse']
        }),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Profile Information', {
            'fields': ('user_type', 'phone_number', 'preferred_currency'),
            'classes': ['wide']
        }),
    )
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}" if obj.first_name else "-"
    get_full_name.short_description = "Full Name"
    get_full_name.admin_order_field = 'first_name'
    
    def get_review_count(self, obj):
        try:
            count = obj.reviews.count()
        except:
            count = 0
        return format_html('<b style="color: #28a745;">{}</b>', count)
    get_review_count.short_description = "Reviews"
    
    def date_joined_display(self, obj):
        return obj.date_joined.strftime("%b %d, %Y")
    date_joined_display.short_description = "Joined"
    date_joined_display.admin_order_field = 'date_joined'
    
    actions = ['activate_users', 'deactivate_users', 'make_travelers', 'make_guides']
    
    def activate_users(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} users activated.")
    activate_users.short_description = "Activate selected users"
    
    def deactivate_users(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} users deactivated.")
    deactivate_users.short_description = "Deactivate selected users"
    
    def make_travelers(self, request, queryset):
        queryset.update(user_type='traveler')
        self.message_user(request, f"{queryset.count()} users updated to Travelers.")
    make_travelers.short_description = "Set user type to Traveler"
    
    def make_guides(self, request, queryset):
        queryset.update(user_type='guide')
        self.message_user(request, f"{queryset.count()} users updated to Guides.")
    make_guides.short_description = "Set user type to Guide"


@admin.register(Destination)
class DestinationAdmin(admin.ModelAdmin):  # Fixed: directly subclass ModelAdmin
    list_display = [
        'name', 'country', 'continent', 'tour_count', 
        'display_rating', 'review_count', 'is_featured', 
        'is_active', 'created_at'
    ]
    list_filter = ['continent', 'country', 'is_featured', 'is_active']
    search_fields = ['name', 'country', 'description']
    prepopulated_fields = {'slug': ('name', 'country')}
    readonly_fields = ['tour_count', 'visitor_count', 'review_count', 'average_rating']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'continent', 'country', 'short_description', 'description')
        }),
        ('Media', {
            'fields': ('featured_image', 'gallery_images', 'video_url'),
            'classes': ['wide']
        }),
        ('Location Data', {
            'fields': ('latitude', 'longitude'),
            'classes': ['collapse']
        }),
        ('Statistics', {
            'fields': ('tour_count', 'visitor_count', 'average_rating', 'review_count'),
            'classes': ['collapse']
        }),
        ('SEO & Settings', {
            'fields': ('meta_title', 'meta_description', 'is_featured', 'is_active'),
            'classes': ['collapse']
        }),
    )
    
    inlines = [ReviewInline]
    
    def tour_count(self, obj):
        return obj.tour_count
    tour_count.short_description = "Tours"
    
    def display_rating(self, obj):
        rating = obj.average_rating
        stars = '★' * int(rating) + '☆' * (5 - int(rating))
        return format_html(
            '<span style="color: #f39c12;">{}</span> <b style="color: #2c3e50;">({})</b>',
            stars, rating
        )
    display_rating.short_description = "Rating"
    display_rating.admin_order_field = 'average_rating'
    
    actions = ['feature_destinations', 'unfeature_destinations', 'activate_destinations']
    
    def feature_destinations(self, request, queryset):
        queryset.update(is_featured=True)
        self.message_user(request, f"{queryset.count()} destinations featured.")
    feature_destinations.short_description = "Feature selected destinations"
    
    def unfeature_destinations(self, request, queryset):
        queryset.update(is_featured=False)
        self.message_user(request, f"{queryset.count()} destinations unfeatured.")
    unfeature_destinations.short_description = "Unfeature selected destinations"
    
    def activate_destinations(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} destinations activated.")
    activate_destinations.short_description = "Activate selected destinations"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):  # Fixed: directly subclass ModelAdmin
    list_display = ['name', 'icon_display', 'tour_count', 'order', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['order', 'name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'icon')
        }),
        ('Settings', {
            'fields': ('featured_image', 'order', 'is_active')
        }),
    )
    
    def icon_display(self, obj):
        return format_html('<i class="{}" style="font-size: 1.2rem;"></i>', obj.icon)
    icon_display.short_description = "Icon"
    
    def tour_count(self, obj):
        try:
            count = obj.tours.count()
            url = reverse('admin:safarisite_tour_changelist') + f'?categories__id__exact={obj.id}'
            return format_html('<a href="{}"><b>{}</b></a>', url, count)
        except:
            return 0
    tour_count.short_description = "Tours"


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):  # Fixed: directly subclass ModelAdmin
    list_display = ['name', 'tour_count']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}
    
    def tour_count(self, obj):
        try:
            return obj.tours.count()
        except:
            return 0
    tour_count.short_description = "Tours"


@admin.register(Tour)
class TourAdmin(admin.ModelAdmin):  # Fixed: directly subclass ModelAdmin
    list_display = [
        'title', 'destination_link', 'display_price', 'duration_days', 
        'display_rating', 'review_count', 'booking_count', 'is_featured', 
        'is_active'
    ]
    list_filter = [
        'destination', 'categories', 'difficulty_level', 
        'is_featured', 'is_trending', 'is_active'
    ]
    search_fields = ['title', 'overview']
    prepopulated_fields = {'slug': ('title', 'destination')}
    readonly_fields = ['view_count', 'booking_count', 'review_count', 'average_rating']
    filter_horizontal = ['categories', 'tags']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'destination', 'categories', 'tags', 'overview')
        }),
        ('Itinerary & Details', {
            'fields': ('itinerary', 'inclusions', 'exclusions', 'packing_list'),
            'classes': ['wide']
        }),
        ('Media', {
            'fields': ('featured_image', 'gallery_images', 'video_url'),
            'classes': ['wide']
        }),
        ('Pricing', {
            'fields': ('price_per_person', 'price_currency', 'discount_price'),
            'classes': ['collapse']
        }),
        ('Duration & Group', {
            'fields': ('duration_days', 'duration_nights', 'min_group_size', 'max_group_size'),
            'classes': ['collapse']
        }),
        ('Ratings & Difficulty', {
            'fields': ('difficulty_level', 'physical_rating', 'cultural_rating', 
                      'wildlife_rating', 'adventure_rating'),
            'classes': ['collapse']
        }),
        ('Location & Meeting', {
            'fields': ('meeting_point', 'meeting_point_coordinates', 'departure_times'),
            'classes': ['collapse']
        }),
        ('Availability', {
            'fields': ('available_from', 'available_to', 'booked_dates'),
            'classes': ['collapse']
        }),
        ('Statistics', {
            'fields': ('view_count', 'booking_count', 'average_rating', 'review_count'),
            'classes': ['collapse']
        }),
        ('SEO & Settings', {
            'fields': ('meta_title', 'meta_description', 'created_by', 
                      'is_featured', 'is_trending', 'is_active'),
            'classes': ['collapse']
        }),
    )
    
    inlines = [TourDateInline, ReviewInline, BookingInline]
    
    def destination_link(self, obj):
        url = reverse('admin:safarisite_destination_change', args=[obj.destination.id])
        return format_html('<a href="{}">{}</a>', url, obj.destination.name)
    destination_link.short_description = "Destination"
    destination_link.admin_order_field = 'destination'
    
    def display_price(self, obj):
        if obj.discount_price:
            return format_html(
                '<span style="text-decoration: line-through; color: #999;">${}</span> '
                '<span style="color: #27ae60; font-weight: bold;">${}</span>',
                obj.price_per_person, obj.discount_price
            )
        return format_html('<b>${}</b>', obj.price_per_person)
    display_price.short_description = "Price"
    display_price.admin_order_field = 'price_per_person'
    
    def display_rating(self, obj):
        rating = obj.average_rating
        stars = '★' * int(rating) + '☆' * (5 - int(rating))
        return format_html(
            '<span style="color: #f39c12;">{}</span> <b style="color: #2c3e50;">({})</b>',
            stars, rating
        )
    display_rating.short_description = "Rating"
    display_rating.admin_order_field = 'average_rating'
    
    actions = ['feature_tours', 'make_trending', 'clone_tours']
    
    def feature_tours(self, request, queryset):
        queryset.update(is_featured=True)
        self.message_user(request, f"{queryset.count()} tours featured.")
    feature_tours.short_description = "Feature selected tours"
    
    def make_trending(self, request, queryset):
        queryset.update(is_trending=True)
        self.message_user(request, f"{queryset.count()} tours marked as trending.")
    make_trending.short_description = "Mark as trending"
    
    def clone_tours(self, request, queryset):
        for tour in queryset:
            tour.pk = None
            tour.title = f"{tour.title} (Copy)"
            tour.slug = f"{tour.slug}-copy"
            tour.save()
        self.message_user(request, f"{queryset.count()} tours cloned.")
    clone_tours.short_description = "Clone selected tours"
    
    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# Continue with the rest of the admin classes, making sure each one subclasses admin.ModelAdmin directly
# For example:

@admin.register(TourDate)
class TourDateAdmin(admin.ModelAdmin):
    list_display = ['tour_link', 'start_date', 'end_date', 'availability', 'is_active']
    list_filter = ['is_active', 'start_date']
    search_fields = ['tour__title']
    date_hierarchy = 'start_date'
    
    def tour_link(self, obj):
        url = reverse('admin:safarisite_tour_change', args=[obj.tour.id])
        return format_html('<a href="{}">{}</a>', url, obj.tour.title)
    tour_link.short_description = "Tour"
    
    def availability(self, obj):
        if obj.available_spots == 0:
            return format_html('<span style="color: #dc3545; font-weight: bold;">Fully Booked</span>')
        elif obj.available_spots <= 3:
            return format_html('<span style="color: #fd7e14; font-weight: bold;">{} spots left</span>', obj.available_spots)
        return format_html('<span style="color: #28a745;">{} spots</span>', obj.available_spots)
    availability.short_description = "Availability"


@admin.register(Guide)
class GuideAdmin(admin.ModelAdmin):
    list_display = ['user_link', 'years_experience', 'languages_display',
                   'total_tours_guided', 'display_rating', 'is_verified']
    list_filter = ['is_certified', 'is_verified']
    search_fields = ['user__username', 'user__first_name', 'user__last_name']
    filter_horizontal = ['specializations', 'tours']
    
    def user_link(self, obj):
        url = reverse('admin:safarisite_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name() or obj.user.username)
    user_link.short_description = "Guide Name"
    
    def languages_display(self, obj):
        return ', '.join(obj.languages) if obj.languages else '-'
    languages_display.short_description = "Languages"
    
    def display_rating(self, obj):
        rating = obj.average_rating
        stars = '★' * int(rating) + '☆' * (5 - int(rating))
        return format_html('<span style="color: #f39c12;">{}</span>', stars)
    display_rating.short_description = "Rating"


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['title', 'user_link', 'item_reviewed', 'overall_rating_display', 
                   'helpful_count', 'is_verified', 'is_approved', 'created_at']
    list_filter = ['review_type', 'overall_rating', 'is_verified', 'is_approved', 'created_at']
    search_fields = ['title', 'content', 'user__username']
    date_hierarchy = 'created_at'
    
    def user_link(self, obj):
        url = reverse('admin:safarisite_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = "User"
    
    def item_reviewed(self, obj):
        if obj.tour:
            url = reverse('admin:safarisite_tour_change', args=[obj.tour.id])
            return format_html('<a href="{}">Tour: {}</a>', url, obj.tour.title)
        elif obj.guide:
            url = reverse('admin:safarisite_guide_change', args=[obj.guide.id])
            return format_html('<a href="{}">Guide: {}</a>', url, obj.guide.user.get_full_name())
        elif obj.destination:
            url = reverse('admin:safarisite_destination_change', args=[obj.destination.id])
            return format_html('<a href="{}">Destination: {}</a>', url, obj.destination.name)
        return "-"
    item_reviewed.short_description = "Reviewed Item"
    
    def overall_rating_display(self, obj):
        stars = '★' * obj.overall_rating + '☆' * (5 - obj.overall_rating)
        return format_html('<span style="color: #f39c12;">{}</span>', stars)
    overall_rating_display.short_description = "Rating"


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['booking_reference', 'user_link', 'tour_link', 'tour_date', 
                   'participants_count', 'total_price_display', 'status', 'payment_status']
    list_filter = ['status', 'payment_status', 'booked_at']
    search_fields = ['booking_reference', 'user__username', 'user__email']
    date_hierarchy = 'booked_at'
    readonly_fields = ['booking_reference', 'booked_at', 'updated_at']
    
    def user_link(self, obj):
        url = reverse('admin:safarisite_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = "User"
    
    def tour_link(self, obj):
        url = reverse('admin:safarisite_tour_change', args=[obj.tour.id])
        return format_html('<a href="{}">{}</a>', url, obj.tour.title)
    tour_link.short_description = "Tour"
    
    def participants_count(self, obj):
        return obj.number_of_participants
    participants_count.short_description = "Pax"
    
    def total_price_display(self, obj):
        return format_html('<b>{}{}</b>', obj.currency, obj.total_price)
    total_price_display.short_description = "Total Price"


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ['user_link', 'tour_link', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'tour__title']
    
    def user_link(self, obj):
        url = reverse('admin:safarisite_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = "User"
    
    def tour_link(self, obj):
        url = reverse('admin:safarisite_tour_change', args=[obj.tour.id])
        return format_html('<a href="{}">{}</a>', url, obj.tour.title)
    tour_link.short_description = "Tour"


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'inquiry_type', 'tour_link', 'subject_truncated', 
                   'created_at', 'is_read', 'is_replied']
    list_filter = ['inquiry_type', 'is_read', 'is_replied', 'created_at']
    search_fields = ['name', 'email', 'subject', 'message']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at']
    
    def tour_link(self, obj):
        if obj.tour:
            url = reverse('admin:safarisite_tour_change', args=[obj.tour.id])
            return format_html('<a href="{}">{}</a>', url, obj.tour.title)
        return "-"
    tour_link.short_description = "Tour"
    
    def subject_truncated(self, obj):
        return obj.subject[:50] + '...' if len(obj.subject) > 50 else obj.subject
    subject_truncated.short_description = "Subject"


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ['title', 'author_link', 'destination_link', 'view_count', 
                   'read_time_minutes', 'is_published', 'published_at']
    list_filter = ['is_published', 'is_featured', 'destination', 'created_at']
    search_fields = ['title', 'excerpt', 'content']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_at'
    filter_horizontal = ['tours']
    readonly_fields = ['view_count', 'created_at', 'updated_at']
    
    def author_link(self, obj):
        url = reverse('admin:safarisite_user_change', args=[obj.author.id])
        return format_html('<a href="{}">{}</a>', url, obj.author.get_full_name() or obj.author.username)
    author_link.short_description = "Author"
    
    def destination_link(self, obj):
        if obj.destination:
            url = reverse('admin:safarisite_destination_change', args=[obj.destination.id])
            return format_html('<a href="{}">{}</a>', url, obj.destination.name)
        return "-"
    destination_link.short_description = "Destination"


@admin.register(BlogComment)
class BlogCommentAdmin(admin.ModelAdmin):
    list_display = ['id', 'post', 'display_name', 'parent', 'is_deleted', 'created_at']
    list_filter = ['is_deleted', 'created_at']
    search_fields = ['content', 'guest_name', 'user__username', 'post__title']
    readonly_fields = ['owner_token', 'created_at', 'updated_at']

    def display_name(self, obj):
        return obj.display_name
    display_name.short_description = "Author"


@admin.register(BlogCommentReaction)
class BlogCommentReactionAdmin(admin.ModelAdmin):
    list_display = ['comment', 'reaction_type', 'user', 'actor_token', 'created_at']
    list_filter = ['reaction_type', 'created_at']
    search_fields = ['comment__content', 'user__username', 'actor_token']


@admin.register(BlogPostView)
class BlogPostViewAdmin(admin.ModelAdmin):
    list_display = ['post', 'user', 'viewer_token', 'ip_address', 'created_at']
    list_filter = ['created_at']
    search_fields = ['post__title', 'user__username', 'viewer_token', 'ip_address']


@admin.register(BlogPostShare)
class BlogPostShareAdmin(admin.ModelAdmin):
    list_display = ['post', 'channel', 'user', 'actor_token', 'created_at']
    list_filter = ['channel', 'created_at']
    search_fields = ['post__title', 'user__username', 'actor_token']


@admin.register(BlogPostReaction)
class BlogPostReactionAdmin(admin.ModelAdmin):
    list_display = ['post', 'reaction_type', 'user', 'actor_token', 'created_at']
    list_filter = ['reaction_type', 'created_at']
    search_fields = ['post__title', 'user__username', 'actor_token']


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ['email', 'first_name', 'is_active', 'subscribed_at']
    list_filter = ['is_active', 'subscribed_at']
    search_fields = ['email', 'first_name']
    date_hierarchy = 'subscribed_at'
    filter_horizontal = ['preferred_destinations', 'preferred_categories']


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ['site_name', 'contact_email', 'contact_phone']
    
    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ['question', 'category', 'order', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['question', 'answer']
    list_editable = ['order', 'is_active']


# Customize Admin Site
admin.site.site_header = "Safari Discoveries Administration"
admin.site.site_title = "Safari Discoveries Admin"
admin.site.index_title = "Welcome to Safari Discoveries Dashboard"
