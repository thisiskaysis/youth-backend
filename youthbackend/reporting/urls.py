from django.urls import path

from . import views

urlpatterns = [
    path('dashboard/', views.DashboardView.as_view(), name='reporting-dashboard'),
    path('attendance-trend/', views.AttendanceTrendView.as_view(), name='reporting-attendance-trend'),
    path('roster-summary/', views.RosterSummaryView.as_view(), name='reporting-roster-summary'),
    path('attendance/', views.AttendanceDrilldownView.as_view(), name='reporting-attendance'),
    path('first-time-visitors/', views.FirstTimeVisitorsView.as_view(), name='reporting-first-time-visitors'),
    path('unassigned-youth/', views.UnassignedYouthView.as_view(), name='reporting-unassigned-youth'),
    path('decisions/', views.DecisionsDrilldownView.as_view(), name='reporting-decisions'),
    path('outstanding-followups/', views.OutstandingFollowUpsView.as_view(), name='reporting-outstanding-followups'),
    path('outstanding-consent/', views.OutstandingConsentView.as_view(), name='reporting-outstanding-consent'),
    path('rides/', views.RidesDrilldownView.as_view(), name='reporting-rides'),
]
