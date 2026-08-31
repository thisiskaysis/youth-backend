from django.db import transaction

from notifications.catalog import Category, NotificationType
from notifications.services import notify

from .models import FormAssignment, FormSubmission


class FormError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


@transaction.atomic
def assign_form(form, people, actor, due_at=None):
    """Create an assignment for each person who doesn't already have one -
    never duplicate an outstanding requirement, and never silently
    overwrite an existing submission."""
    created = []
    existing_person_ids = set(
        FormAssignment.objects.filter(form=form, person__in=people).values_list('person_id', flat=True)
    )
    for person in people:
        if person.id in existing_person_ids:
            continue
        assignment = FormAssignment.objects.create(form=form, person=person, due_at=due_at, assigned_by=actor)
        created.append(assignment)

    for assignment in created:
        notify(
            assignment.person, Category.FORMS, NotificationType.FORM_ASSIGNED,
            title=f'New form to complete: {form.title}',
            body=form.description or 'Please complete this as soon as you can.',
            deep_link_type='form_assignment', deep_link_id=assignment.id,
            data={'assignment_id': assignment.id},
        )
    return created


def submit_form(assignment, person, answers):
    if assignment.person_id != person.id:
        raise FormError('NOT_YOUR_ASSIGNMENT', 'This form was not assigned to you.')
    if assignment.status == FormAssignment.Status.SUBMITTED:
        raise FormError('ALREADY_SUBMITTED', 'This form has already been submitted.')

    submission = FormSubmission.objects.create(assignment=assignment, answers=answers, submitted_by=person)
    assignment.status = FormAssignment.Status.SUBMITTED
    assignment.save(update_fields=['status'])
    return submission
