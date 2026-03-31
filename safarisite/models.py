from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
from django.urls import reverse

class User(AbstractUser):
    """Custom User model for travelers and guides"""
    USER_TYPES = (
        ('traveler', 'Traveler'),
        ('guide', 'Guide'),
        ('operator', 'Tour Operator'),
        ('admin', 'Administrator'),
    )
    
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default='traveler')
    profile_image = models.ImageField(upload_to='profiles/', null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    preferred_currency = models.CharField(max_length=3, default='USD')
    newsletter_subscription = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Add these lines to fix the reverse accessor clashes
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name="custom_user_set",
        related_query_name="custom_user",
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name="custom_user_set",
        related_query_name="custom_user",
    )
    
    def __str__(self):
        return f"{self.username} - {self.get_user_type_display()}"

class Destination(models.Model):
    """Main destinations/cities/countries"""
    CONTINENTS = (
        ('africa', 'Africa'),
        ('asia', 'Asia'),
        ('europe', 'Europe'),
        ('north_america', 'North America'),
        ('south_america', 'South America'),
        ('oceania', 'Oceania'),
    )
    
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    continent = models.CharField(max_length=20, choices=CONTINENTS, default='africa')
    country = models.CharField(max_length=100)
    description = models.TextField()
    short_description = models.CharField(max_length=200)
    featured_image = models.ImageField(upload_to='destinations/')
    gallery_images = models.JSONField(default=list, blank=True)  # Store array of image URLs
    video_url = models.URLField(blank=True, null=True)
    
    # Location data
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Stats
    tour_count = models.IntegerField(default=0)
    visitor_count = models.IntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    review_count = models.IntegerField(default=0)
    
    # SEO
    meta_title = models.CharField(max_length=60, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    
    # Flags
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['continent', 'country']),
            models.Index(fields=['is_featured']),
        ]
    
    def __str__(self):
        return f"{self.name}, {self.country}"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.name}-{self.country}")
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('destination_detail', args=[self.slug])

class Category(models.Model):
    """Tour categories like Safari, Beach, Adventure, etc."""
    name = models.CharField(max_length=50)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, help_text="Font Awesome icon class")
    featured_image = models.ImageField(upload_to='categories/', null=True, blank=True)
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Tag(models.Model):
    """Tags for filtering and search"""
    name = models.CharField(max_length=50)
    slug = models.SlugField(unique=True)
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Tour(models.Model):
    """Main tour/experience model"""
    DIFFICULTY_LEVELS = (
        ('easy', 'Easy'),
        ('moderate', 'Moderate'),
        ('challenging', 'Challenging'),
        ('difficult', 'Difficult'),
    )
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE, related_name='tours')
    categories = models.ManyToManyField(Category, related_name='tours')
    tags = models.ManyToManyField(Tag, blank=True, related_name='tours')
    
    # Description
    overview = models.TextField()
    itinerary = models.JSONField(default=list)  # Store day-by-day itinerary
    inclusions = models.JSONField(default=list)  # What's included
    exclusions = models.JSONField(default=list)  # What's not included
    packing_list = models.JSONField(default=list, blank=True)  # Recommended items to pack
    
    # Media
    featured_image = models.ImageField(upload_to='tours/')
    gallery_images = models.JSONField(default=list, blank=True)
    video_url = models.URLField(blank=True, null=True)
    
    # Pricing
    price_per_person = models.DecimalField(max_digits=10, decimal_places=2)
    price_currency = models.CharField(max_length=3, default='USD')
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    min_age = models.IntegerField(default=0)
    max_age = models.IntegerField(null=True, blank=True)
    
    # Duration
    duration_days = models.IntegerField(validators=[MinValueValidator(1)])
    duration_nights = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    
    # Group info
    min_group_size = models.IntegerField(default=1)
    max_group_size = models.IntegerField(default=20)
    
    # Location
    meeting_point = models.TextField()
    meeting_point_coordinates = models.JSONField(default=dict, blank=True)
    departure_times = models.JSONField(default=list)  # Available departure times
    
    # Difficulty and requirements
    difficulty_level = models.CharField(max_length=20, choices=DIFFICULTY_LEVELS, default='moderate')
    physical_rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], default=3)
    cultural_rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], default=3)
    wildlife_rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], default=3)
    adventure_rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], default=3)
    
    # Availability
    available_from = models.DateField()
    available_to = models.DateField()
    booked_dates = models.JSONField(default=list, blank=True)  # Dates that are fully booked
    
    # Stats
    view_count = models.IntegerField(default=0)
    booking_count = models.IntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    review_count = models.IntegerField(default=0)
    
    # SEO
    meta_title = models.CharField(max_length=60, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    
    # Flags
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_trending = models.BooleanField(default=False)
    
    # Timestamps
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_tours')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_featured', '-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['destination', 'is_active']),
            models.Index(fields=['price_per_person']),
            models.Index(fields=['duration_days']),
            models.Index(fields=['average_rating']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.title}-{self.destination.name}")
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('tour_detail', args=[self.slug])
    
    @property
    def final_price(self):
        return self.discount_price if self.discount_price else self.price_per_person

class TourDate(models.Model):
    """Specific tour departure dates with availability"""
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name='tour_dates')
    start_date = models.DateField()
    end_date = models.DateField()
    available_spots = models.IntegerField(validators=[MinValueValidator(0)])
    total_spots = models.IntegerField()
    is_active = models.BooleanField(default=True)
    special_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    class Meta:
        ordering = ['start_date']
        indexes = [
            models.Index(fields=['start_date', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.tour.title} - {self.start_date}"
    
    @property
    def is_available(self):
        return self.available_spots > 0 and self.is_active
    
    @property
    def booked_spots(self):
        return self.total_spots - self.available_spots

class Guide(models.Model):
    """Tour guides"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='guide_profile')
    tours = models.ManyToManyField(Tour, related_name='guides', blank=True)
    
    # Professional info
    license_number = models.CharField(max_length=50, blank=True)
    years_experience = models.IntegerField(default=0)
    specializations = models.ManyToManyField(Category, related_name='specialized_guides', blank=True)
    languages = models.JSONField(default=list)  # List of languages spoken
    
    # Verification
    is_certified = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Stats
    total_tours_guided = models.IntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    review_count = models.IntegerField(default=0)
    
    # Timestamps
    joined_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Guide: {self.user.get_full_name()}"

class Review(models.Model):
    """User reviews for tours and guides"""
    REVIEW_TYPES = (
        ('tour', 'Tour Review'),
        ('guide', 'Guide Review'),
        ('destination', 'Destination Review'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name='reviews', null=True, blank=True)
    guide = models.ForeignKey(Guide, on_delete=models.CASCADE, related_name='reviews', null=True, blank=True)
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE, related_name='reviews', null=True, blank=True)
    
    review_type = models.CharField(max_length=20, choices=REVIEW_TYPES)
    
    # Ratings
    overall_rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    value_rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    guide_rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True)
    organization_rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True)
    
    # Content
    title = models.CharField(max_length=100)
    content = models.TextField()
    pros = models.TextField(blank=True)
    cons = models.TextField(blank=True)
    
    # Media
    images = models.JSONField(default=list, blank=True)
    
    # Verification
    is_verified = models.BooleanField(default=False)
    verified_purchase = models.BooleanField(default=False)
    helpful_count = models.IntegerField(default=0)
    
    # Moderation
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='approved_reviews')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['review_type', 'is_approved']),
            models.Index(fields=['overall_rating']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"

class Booking(models.Model):
    """User bookings"""
    BOOKING_STATUS = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
        ('refunded', 'Refunded'),
    )
    
    booking_reference = models.CharField(max_length=20, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name='bookings')
    tour_date = models.ForeignKey(TourDate, on_delete=models.CASCADE, related_name='bookings')
    
    # Booking details
    number_of_participants = models.IntegerField(validators=[MinValueValidator(1)])
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    status = models.CharField(max_length=20, choices=BOOKING_STATUS, default='pending')
    
    # Participant details
    participants = models.JSONField(default=list)  # Store names, ages, special requirements
    special_requirements = models.TextField(blank=True)
    
    # Payment
    payment_method = models.CharField(max_length=50, blank=True)
    payment_status = models.BooleanField(default=False)
    payment_date = models.DateTimeField(null=True, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)
    
    # Timestamps
    booked_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-booked_at']
        indexes = [
            models.Index(fields=['booking_reference']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['tour_date']),
        ]
    
    def __str__(self):
        return f"Booking {self.booking_reference} - {self.user.username}"
    
    def save(self, *args, **kwargs):
        if not self.booking_reference:
            # Generate unique booking reference
            import uuid
            self.booking_reference = f"BK-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

class Wishlist(models.Model):
    """User wishlist items"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist')
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name='wishlisted_by')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'tour']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.tour.title}"

class Inquiry(models.Model):
    """User inquiries about tours"""
    INQUIRY_TYPES = (
        ('general', 'General Question'),
        ('booking', 'Booking Question'),
        ('custom', 'Custom Tour Request'),
        ('group', 'Group Booking'),
        ('corporate', 'Corporate Event'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='inquiries', null=True, blank=True)
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name='inquiries', null=True, blank=True)
    
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    inquiry_type = models.CharField(max_length=20, choices=INQUIRY_TYPES, default='general')
    
    subject = models.CharField(max_length=200)
    message = models.TextField()
    
    preferred_date = models.DateField(null=True, blank=True)
    number_of_people = models.IntegerField(null=True, blank=True)
    
    # Status
    is_read = models.BooleanField(default=False)
    is_replied = models.BooleanField(default=False)
    replied_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='replied_inquiries')
    replied_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Inquiries"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Inquiry from {self.name} - {self.subject}"

class BlogPost(models.Model):
    """Travel blog posts for content marketing"""
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blog_posts')
    destination = models.ForeignKey(Destination, on_delete=models.SET_NULL, null=True, related_name='blog_posts')
    tours = models.ManyToManyField(Tour, blank=True, related_name='blog_posts')
    
    # Content
    excerpt = models.CharField(max_length=300)
    content = models.TextField()
    featured_image = models.ImageField(upload_to='blog/')
    gallery_images = models.JSONField(default=list, blank=True)
    
    # Stats
    view_count = models.IntegerField(default=0)
    read_time_minutes = models.IntegerField(default=5)
    
    # SEO
    meta_title = models.CharField(max_length=60, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    
    # Flags
    is_featured = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)
    
    # Timestamps
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-published_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_published', 'published_at']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class BlogPostView(models.Model):
    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='tracked_views')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='blog_post_views')
    viewer_token = models.CharField(max_length=120)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['post', 'viewer_token'], name='unique_blog_post_view'),
        ]

    def __str__(self):
        return f"{self.post.title} view"


class BlogPostShare(models.Model):
    CHANNEL_CHOICES = (
        ('facebook', 'Facebook'),
        ('whatsapp', 'WhatsApp'),
        ('x', 'X'),
        ('linkedin', 'LinkedIn'),
        ('telegram', 'Telegram'),
        ('email', 'Email'),
    )

    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='shares')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='blog_post_shares')
    actor_token = models.CharField(max_length=120)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['post', 'channel', 'created_at']),
        ]

    def __str__(self):
        return f"{self.post.title} shared via {self.channel}"


class BlogPostReaction(models.Model):
    REACTION_CHOICES = (
        ('like', '👍'),
        ('love', '❤️'),
        ('wow', '🔥'),
        ('laugh', '😂'),
    )

    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='blog_post_reactions')
    actor_token = models.CharField(max_length=120)
    reaction_type = models.CharField(max_length=20, choices=REACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        constraints = [
            models.UniqueConstraint(fields=['post', 'actor_token'], name='unique_post_reactor'),
        ]

    def __str__(self):
        return f"{self.get_reaction_type_display()} on {self.post.title}"


class BlogComment(models.Model):
    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='blog_comments')
    guest_name = models.CharField(max_length=80, blank=True)
    owner_token = models.CharField(max_length=120)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    content = models.TextField(max_length=1200)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['post', 'parent', 'created_at']),
        ]

    def __str__(self):
        return f"Comment on {self.post.title}"

    @property
    def display_name(self):
        if self.user:
            return self.user.get_full_name() or self.user.username
        return self.guest_name or 'Explorer'


class BlogCommentReaction(models.Model):
    REACTION_CHOICES = (
        ('like', '👍'),
        ('love', '❤️'),
        ('fire', '🔥'),
        ('laugh', '😂'),
    )

    comment = models.ForeignKey(BlogComment, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='blog_comment_reactions')
    actor_token = models.CharField(max_length=120)
    reaction_type = models.CharField(max_length=20, choices=REACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        constraints = [
            models.UniqueConstraint(fields=['comment', 'actor_token'], name='unique_comment_reactor'),
        ]

    def __str__(self):
        return f"{self.get_reaction_type_display()} on comment {self.comment_id}"

class NewsletterSubscriber(models.Model):
    """Newsletter subscribers"""
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    
    # Preferences
    preferred_destinations = models.ManyToManyField(Destination, blank=True)
    preferred_categories = models.ManyToManyField(Category, blank=True)
    
    def __str__(self):
        return self.email

class SiteSettings(models.Model):
    """Global site settings"""
    site_name = models.CharField(max_length=100, default='Safari Discoveries')
    site_description = models.TextField(blank=True)
    
    # Contact info
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20)
    address = models.TextField(blank=True)
    
    # Social media
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    pinterest_url = models.URLField(blank=True)
    
    # SEO
    google_analytics_id = models.CharField(max_length=50, blank=True)
    meta_keywords = models.TextField(blank=True)
    
    # Currency
    default_currency = models.CharField(max_length=3, default='USD')
    available_currencies = models.JSONField(default=list)
    
    # Theme
    primary_color = models.CharField(max_length=7, default='#1e4b6e')
    accent_color = models.CharField(max_length=7, default='#f5923e')
    
    # Features
    enable_reviews = models.BooleanField(default=True)
    enable_wishlist = models.BooleanField(default=True)
    enable_newsletter = models.BooleanField(default=True)
    
    class Meta:
        verbose_name_plural = "Site Settings"
    
    def __str__(self):
        return self.site_name

class FAQ(models.Model):
    """Frequently Asked Questions"""
    question = models.CharField(max_length=200)
    answer = models.TextField()
    category = models.CharField(max_length=50, blank=True)
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['order', 'question']
    
    def __str__(self):
        return self.question
