from rest_framework import serializers

from .models import ContentItem


class ContentItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentItem
        fields = [
            'id', 'title', 'body', 'image', 'cta_label', 'cta_url', 'status',
            'publish_at', 'expire_at', 'audience_everyone', 'audience_groups',
            'audience_school_years', 'created_by', 'created_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at']
