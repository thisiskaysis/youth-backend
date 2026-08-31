from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import FormAssignment, FormDefinition, FormSubmission

User = get_user_model()


class FormDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormDefinition
        fields = ['id', 'title', 'description', 'schema', 'status', 'created_by', 'created_at']
        read_only_fields = ['id', 'created_by', 'created_at']


class FormSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormSubmission
        fields = ['id', 'answers', 'submitted_by', 'created_at']
        read_only_fields = fields


class FormAssignmentSerializer(serializers.ModelSerializer):
    form_title = serializers.CharField(source='form.title', read_only=True)
    # The assignee has no access to the leader/admin-only definitions
    # endpoint, so the schema needed to render the form is exposed here.
    form_description = serializers.CharField(source='form.description', read_only=True)
    form_schema = serializers.JSONField(source='form.schema', read_only=True)
    submission = FormSubmissionSerializer(read_only=True)

    class Meta:
        model = FormAssignment
        fields = [
            'id', 'form', 'form_title', 'form_description', 'form_schema',
            'person', 'due_at', 'status', 'submission', 'created_at',
        ]
        read_only_fields = [
            'id', 'form', 'form_title', 'form_description', 'form_schema',
            'person', 'status', 'submission', 'created_at',
        ]


class AssignFormInputSerializer(serializers.Serializer):
    person_ids = serializers.PrimaryKeyRelatedField(many=True, queryset=User.objects.all())
    due_at = serializers.DateTimeField(required=False, allow_null=True)


class SubmitFormInputSerializer(serializers.Serializer):
    answers = serializers.DictField(required=False, default=dict)
