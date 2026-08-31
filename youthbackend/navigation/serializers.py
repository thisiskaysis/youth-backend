from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator
from rest_framework import serializers

from .models import NavigationItem


class NavigationItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = NavigationItem
        fields = [
            'id', 'label', 'icon', 'destination_type', 'destination_value', 'destination_id',
            'sort_order', 'status', 'publish_at', 'expire_at', 'is_protected',
            'audience_everyone', 'audience_groups', 'audience_school_years',
            'created_by', 'created_at',
        ]
        # sort_order only ever changes via the dedicated reorder action -
        # docs explicitly warn against staff editing sort-order numbers.
        read_only_fields = ['id', 'sort_order', 'created_by', 'created_at']

    def validate(self, attrs):
        destination_type = attrs.get('destination_type', getattr(self.instance, 'destination_type', None))

        if destination_type == NavigationItem.DestinationType.EXTERNAL_URL:
            value = attrs.get('destination_value', getattr(self.instance, 'destination_value', ''))
            try:
                URLValidator()(value)
            except DjangoValidationError:
                raise serializers.ValidationError({'destination_value': 'Must be a valid URL for an external link.'})
        elif destination_type and destination_type != NavigationItem.DestinationType.INTERNAL_SCREEN:
            destination_id = attrs.get('destination_id', getattr(self.instance, 'destination_id', ''))
            if not destination_id:
                raise serializers.ValidationError({'destination_id': 'Required for this destination type.'})

        return attrs
