from django.shortcuts import render, get_object_or_404, render_to_response
from django.http import HttpResponse, HttpResponseRedirect
from django.core.urlresolvers import reverse
from rest_framework import viewsets
from .serializers import SwipeSerializer,UserSerializer,KeySerializer
from .models import Swipe, Key, Session,ProjectSeparation, Project, Holiday
from django.contrib.auth.models import User
from django.views.generic import ListView, DetailView
from django.contrib.auth.decorators import login_required
from rest_framework import permissions
from datetime import datetime, date, timedelta
from .forms import ProjectSeparationForm, SwipeEditForm, HolidayRequestForm, HolidayVerifyForm
from django.utils import timezone
from django.db.models import Q
import locale
from calendar import monthrange
from django.db.models import Prefetch
from attendance.utils import get_quota_work_hours, get_num_of_elapsed_workdays_in_month, get_number_of_work_days, last_month, daily_hours
from czech_holidays import holidays as czech_holidays
from django.template.loader import render_to_string
from weasyprint import HTML
import tempfile

@login_required(login_url='/login/')
def home_page(request):
    return HttpResponseRedirect(reverse(user, args=[request.user.username]))
class SwipeViewSet(viewsets.ModelViewSet):
    '''
    API end point for posting swipes
    '''
    queryset = Swipe.objects.all().order_by("-datetime")[:20]
    serializer_class = SwipeSerializer
    http_method_names = ['post','get']
    permission_classes = (permissions.IsAuthenticated,)

class KeyViewSet(viewsets.ModelViewSet):
    queryset = Key.objects.all()
    serializer_class = KeySerializer
    http_method_names = ['get',]
    permission_classes = (permissions.IsAuthenticated,)

def user_check(request, username):
    #superuser should be able to see all profiles
    if request.user.get_username() == username or request.user.is_superuser or request.user.is_staff:
        return True
    else:
        return False

@login_required(login_url='/login/')
def user(request, username):
    if not user_check(request, username):
        return HttpResponse("Restricted to " + username)
    if request.method == "POST":
        if request.POST.get("IN"):
            Swipe.objects.create(
                    swipe_type = "IN",
                    user = request.user,
                    datetime = timezone.now(),
            )
        if request.POST.get("OUT"):
            Swipe.objects.create(
                    swipe_type = "OUT",
                    user = request.user,
                    datetime = timezone.now(),
            )
        if request.POST.get("OBR"):
            Swipe.objects.create(
                    swipe_type = "OBR",
                    user = request.user,
                    datetime = timezone.now(),
            )
        if request.POST.get("FBR"):
            Swipe.objects.create(
                    swipe_type = "FBR",
                    user = request.user,
                    datetime = timezone.now(),
            )
        if request.POST.get("OTR"):
            Swipe.objects.create(
                    swipe_type = "OTR",
                    user = request.user,
                    datetime = timezone.now(),
            )
        if request.POST.get("FTR"):
            Swipe.objects.create(
                    swipe_type = "FTR",
                    user = request.user,
                    datetime = timezone.now(),
            )
        if request.POST.get("OUTUSER"):
            if (request.user.is_staff)or(request.user.is_superuser):
                if request.POST.get("OUTUSER")=="SwipeUserOut":
                    Swipe.objects.create(
                          swipe_type = "OUT",
                          user = User.objects.get(username=(request.POST.get("username"))),
                          datetime = timezone.now(),
                    )
                elif request.POST.get("OUTUSER")=="BreakUserOut":
                    Swipe.objects.create(
                          swipe_type = "FBR",
                          user = User.objects.get(username=(request.POST.get("username"))),
                          datetime = timezone.now(),
                    )
                    Swipe.objects.create(
                          swipe_type = "OUT",
                          user = User.objects.get(username=(request.POST.get("username"))),
                          datetime = timezone.now(),
                    )
                elif request.POST.get("OUTUSER")=="TripUserOut":
                    Swipe.objects.create(
                          swipe_type = "FTR",
                          user = User.objects.get(username=(request.POST.get("username"))),
                          datetime = timezone.now(),
                    )
                    Swipe.objects.create(
                          swipe_type = "OUT",
                          user = User.objects.get(username=(request.POST.get("username"))),
                          datetime = timezone.now(),
                    )
        return HttpResponseRedirect(reverse(user, args=[request.user.username])); # hard reload the page without any forms
    u = User.objects.get(username=username)
    s = Session.objects.get_sessions_this_month(user=u)
    
    holidays = Holiday.objects.filter(verified = True)

    open_sessions = Session.objects.get_open_sessions()
    try:
        current_session = open_sessions.filter(user=u)[0]
        current_session_work_hours = current_session.session_duration().seconds / 3600
    except:
        current_session = None
        current_session_work_hours = 0

    latest_swipes = []

    for session in open_sessions:
        latest_swipes.append(
            Swipe.objects.filter(session=session).order_by("-datetime")[0]
        )

    at_work_users, on_break_users, on_trip_users, on_holidays_users = [], [], [], []

    for swipe in latest_swipes:
        if swipe.swipe_type == "IN" or swipe.swipe_type == "FBR" or swipe.swipe_type == "FTR":
            at_work_users.append(swipe.user)
        elif swipe.swipe_type == "OBR":
            on_break_users.append(swipe.user)
        elif swipe.swipe_type == "OTR":
            on_trip_users.append(swipe.user)

    for holiday in holidays:
        aware_date_since = timezone.make_aware(datetime.combine(holiday.date_since, datetime.min.time()), timezone.get_current_timezone())
        aware_date_to = timezone.make_aware(datetime.combine(holiday.date_to, datetime.min.time()), timezone.get_current_timezone())
        if (aware_date_since < timezone.now() and aware_date_to > timezone.now()):
            on_holidays_users.append(holiday.profile.user)
    try:
        last_swipe = Swipe.objects.filter(user=u).order_by("-datetime")[0]
        next_swipes = last_swipe.get_next_allowed_types()
    except IndexError:
        last_swipe = None
        next_swipes = ('IN',)  # empty database - first swipe is IN

    last_month_ = last_month()
    if last_month == 12:
        year = datetime.now().year - 1
    else:
        year = datetime.now().year
    
    curent_user_have_profile = False
    if hasattr(u, "profile"):
        curent_user_have_profile = True
        workhours_per_day = u.profile.get_hours_quota()
    else:
        workhours_per_day = 8
    
    holihours = 0
    holihours_aviable = 0
    holihours_requared = 0
    holiday_alert = False
    holidays_month = 0
    holidays_last_month = 0
    if curent_user_have_profile and workhours_per_day != 0:
        holihours = u.profile.get_hours_of_holidays()       
        holihours_requared = u.profile.get_hours_of_holidays(verified = False)
        holihours_aviable = u.profile.get_hours_of_holidays_aviable_to_take()
        holiday_alert = u.profile.need_for_holiday()
        holidays_month = Holiday.objects.get_holidays_hours_this_month(u.profile)
        holidays_last_month = Holiday.objects.get_holidays_hours_month(u.profile, last_month_, year)
    holidays_requared = holihours_requared / max(1,workhours_per_day)
    holidays_aviable = holihours_aviable / max(1,workhours_per_day)
    holidays = holihours / max(1,workhours_per_day)

    hours_total_last_month = Session.objects.get_hours_month(u.id, last_month_, year) + holidays_last_month
    hours_unassigned_last_month = Session.objects.get_unassigned_hours_month(u.id, last_month_, year)
    hours_total_this_month = Session.objects.get_hours_this_month(u.id) + holidays_month
    hours_unassigned_this_month = Session.objects.get_unassigned_hours_month(u.id, datetime.now().month, year)
    hours_not_work_this_month = Session.objects.get_not_work_hours_month(u.id, datetime.now().month, datetime.now().year)
    hours_not_work_last_month = Session.objects.get_not_work_hours_month(u.id, last_month_, year)
    hours_work_last_month = hours_total_last_month - hours_unassigned_last_month - hours_not_work_last_month - holidays_last_month
    hours_work_this_month = hours_total_this_month - hours_unassigned_this_month - hours_not_work_this_month - holidays_month
    
    hours_work_this_year = Session.objects.get_hours_this_year(u.id)
    
    num_of_workdays = get_number_of_work_days(date.today().year, date.today().month)
    unassigned_closed_session_hours = hours_unassigned_this_month - current_session_work_hours
    hours_quota = get_quota_work_hours(datetime.now().year, datetime.now().month, workhours_per_day)
    num_of_elapsed_workdays = get_num_of_elapsed_workdays_in_month(date.today())
    current_quota = num_of_elapsed_workdays * workhours_per_day
    quota_difference = hours_work_this_month + holidays_month + unassigned_closed_session_hours - current_quota
    quota_difference_abs = abs(quota_difference)
    avg_work_hours_fullfill_quota = daily_hours((hours_quota - unassigned_closed_session_hours - hours_work_this_month - holidays_month) / max(1,num_of_workdays - num_of_elapsed_workdays))
    

    context = {
        "user": u,
        "session_list": s,
        "hours_total_this_month": hours_total_this_month,
        "hours_unassigned_this_month": hours_unassigned_this_month,
        "last_swipe": last_swipe,
        "next_swipes": next_swipes,
        "at_work_users": at_work_users,
        "on_break_users": on_break_users,
        "on_trip_users": on_trip_users,
        "on_holidays_users": on_holidays_users,
        "hours_total_last_month": hours_total_last_month,
        "hours_unassigned_last_month": hours_unassigned_last_month,
        "hours_not_work_this_month": hours_not_work_this_month,
        "hours_not_work_last_month": hours_not_work_last_month,
        "hours_work_last_month": hours_work_last_month,
        "hours_work_this_month": hours_work_this_month,
        "hours_quota": hours_quota,
        "current_session_work_hours": current_session_work_hours,
        "current_session": current_session,
        "unassigned_closed_session_hours": unassigned_closed_session_hours,
        "num_of_elapsed_workdays": num_of_elapsed_workdays,
        "num_of_workdays": num_of_workdays,
        "current_quota": current_quota,
        "quota_difference": quota_difference,
        "quota_difference_abs": quota_difference_abs,
        "avg_work_hours_fullfill_qoota": avg_work_hours_fullfill_quota,
        "workhours_per_day": workhours_per_day,
        "taken_holidays": holidays,
        "taken_holihours": holihours,
        "hours_work_this_year": hours_work_this_year,
        "holihours_aviable" :  holihours_aviable,
        "holidays_aviable" :  holidays_aviable,
        "holidays_requared": holidays_requared,
        "holihours_requared": holihours_requared,
        "curent_user_have_profile": curent_user_have_profile,
        "holiday_alert": holiday_alert,
        "holidays_month": holidays_month,
        "holidays_last_month": holidays_last_month
    }
    return render(request, "attendance/user_page.html", context)

@login_required(login_url='/login/')
def sessions(request, username):
    if not user_check(request, username):
        return HttpResponse("Restricted to " + username)
    now =datetime.now()
    year_str = str(now.year)
    month_str = "{:02}".format(now.month)
    return HttpResponseRedirect(
            reverse(sessions_month, args=[request.user.username, year_str, month_str]))


@login_required(login_url='/login/')
def swipes(request, username):
    if not user_check(request, username):
        return HttpResponse("Restricted to " + username)
    swipes = Swipe.objects.filter(
            user__username = username,
            session__isnull = False,
    )

    context = {"swipes":swipes}
    return render(request, "attendance/swipes.html", context)

@login_required(login_url='/login/')
def sessions_month(request, username, year=datetime.now().year, month = datetime.now().month):
    if not user_check(request, username):
        return HttpResponse("Restricted to " + username)
        
    if request.method == "POST":
        if request.POST.get("cancel_holidays"):
            holidays = Holiday.objects.get(id=(request.POST.get("id")))
            holidays.delete()
        else:
            form = ProjectSeparationForm(request.POST)
            if form.is_valid():
                form.save()
                url = reverse('sessions_month', kwargs={"username": username, "year": year, "month": month})
                return HttpResponseRedirect(url)

    u = User.objects.get(username=username)
    in_swipes_ids = Swipe.objects.filter(
        swipe_type="IN",
        user__username=username,
        datetime__month=int(month),
        datetime__year=int(year),
    ).values_list('session', flat=True)
    sessions = Session.objects.filter(pk__in=in_swipes_ids)
    holidays = Holiday.objects.filter(profile = u.profile)
    sessions_and_holidays = []
    for session in sessions:
        sessions_and_holidays.append(session)
    for holiday in holidays:
        if holiday.is_in_month(int(month), int(year)):
            sessions_and_holidays.append(holiday)
            dur = holiday.get_hours_month(month = month, year = year)
            days = dur//holiday.profile.get_hours_quota()
            hours = dur%holiday.profile.get_hours_quota()
            holiday.duration = timedelta(days = days, hours = hours)
            holiday.time_spend = timedelta(days = holiday.hours_spend() // holiday.profile.get_hours_quota())
    sessions_and_holidays.sort(key=lambda x: x.get_date().timestamp())
    separations = ProjectSeparation.objects.filter(session__in=sessions)
    form = ProjectSeparationForm()
    for session in sessions:
        session.form = ProjectSeparationForm(
                initial={
                        "time_spend": session.get_not_assigned_duration(),
                        "session": session.id  # hidden form
                },
        )

    projects = dict()

    for separation in separations:
        if separation.project.name in projects.keys():
            projects[separation.project.name] += separation.time_spend.seconds/3600
        else:
            projects[separation.project.name] = separation.time_spend.seconds/3600
    holihours_requested = 0
    holihours = 0
    if hasattr(u, "profile"):
        workhours_per_day = u.profile.get_hours_quota()
        if workhours_per_day != 0:
            holihours = Holiday.objects.get_holidays_hours_this_month(u.profile)
    else:
        workhours_per_day = 8
        
    not_work_hours = Session.objects.get_not_work_hours_month(u, month, year)
    total_hours = Session.objects.get_hours_month(u.id, month, year) + holihours
    unassigned_hours = Session.objects.get_unassigned_hours_month(u.id, month, year)
    work_hours = total_hours - unassigned_hours - not_work_hours - holihours
    context = {
            "sessions_and_holidays": sessions_and_holidays,
            "year": year,
            "month": month,
            "total_hours": total_hours,
            "unassigned_hours": unassigned_hours,
            "work_hours": work_hours,
            "not_work_hours": not_work_hours,
            "list_of_projects": projects,
            "hours_quota": get_quota_work_hours(int(year), int(month), workhours_per_day),
            "form": form,
            "holihours": holihours
    }
    return render(request, "attendance/sessions.html", context)

@login_required(login_url='/login/')
def session_detail(request, username, id):
    if not user_check(request, username):
        return HttpResponse("Restricted to " + username)
    session = get_object_or_404(Session, pk = int(id))

    if session.user.username == username: #write test for this!!

        separations =  ProjectSeparation.objects.filter(session = session)
        swipes = Swipe.objects.filter(session = session)
        if request.method == "POST":
            form = ProjectSeparationForm(request.POST)
            if form.is_valid():
                form.save()
                url = reverse('session_detail', kwargs={"username": username, "id":id})
                return HttpResponseRedirect(url)

        form = ProjectSeparationForm(
                initial={
                        "time_spend":session.get_not_assigned_duration(),
                        "session": session.id #hidden form
                },
        )

        return_url = reverse("sessions_month", kwargs={
                'username': username,
                'year': str(session.get_date().year),
                'month': "{0:02d}".format(session.get_date().month, '02d'),
        })

        context = {
                "session":session,
                "id":id,
                "project_separation_form": form,
                "separations":separations,
                "swipes":swipes,
                "return_url": return_url,
        }
        return render(request, "attendance/session_detail.html", context)
    else:
        return HttpResponse("Restricted to " + session.user.username)

@login_required(login_url='/login/')
def swipe_detail(request, username, id):
    if not user_check(request, username):
        return HttpResponse("Restricted to " + username)
    swipe = get_object_or_404(Swipe, pk = int(id))

    if swipe.user.username == username: #write test for this!!

        if request.method == "POST":
            form = SwipeEditForm(request.POST, instance = swipe)
            if form.is_valid():
                cleaned_data = form.cleaned_data
                swipe.datetime = cleaned_data["datetime"]
                Swipe.objects.create(
                        user = swipe.user,
                        datetime = cleaned_data["datetime"],
                        swipe_type = swipe.swipe_type,
                        source = "Correction",
                        correction_of_swipe = swipe,
                )
        else:
            form = SwipeEditForm(
                    initial = {
                            "datetime":swipe.datetime,
                    }
            )
        if (swipe.swipe_set.all()):
            corrected_by = swipe.swipe_set.all()[0]
        else:
            corrected_by = None
        context={
                "swipe":swipe,
                "id": id,
                "form": form,
                "corrected_by": corrected_by
        }
        return render(request, "attendance/swipe_detail.html", context)
    else:
        return HttpResponse("Restricted to " + session.user.username)

@login_required(login_url='/login/')
def administrator(request, year=str(datetime.now().year), month="{0:02d}".format(datetime.now().month-1, '02d')):

    if not (request.user.is_superuser or request.user.is_staff):
        return HttpResponse("Restricted to staff.")
    all_users, user_data, empty_users = [], [], []
    users = User.objects.filter().prefetch_related(
        Prefetch(
            'session_set',
            queryset=Session.objects.filter(
                swipe__datetime__month=month,
                swipe__datetime__year=year,
                swipe__swipe_type="IN"
            ).prefetch_related("swipe_set").prefetch_related("projectseparation_set")
        )
    )

    if hasattr(User.objects, "profile"):
        workhours_per_day = User.objects.profile.get_hours_quota()
    else:
        workhours_per_day = 8
        
    for user in users:
        if user.session_set.all():
            user_data.append({
                    "user": user,
                    "hours_total": Session.objects.get_hours_month(user.id, month, int(year), sessions_month=user.session_set.all()),
                    "hours_unassigned": Session.objects.get_unassigned_hours_month(user.id, month, int(year), sessions_month=user.session_set.all()),
                    "hours_not_work": Session.objects.get_not_work_hours_month(user.id, month, int(year), sessions_month=user.session_set.all()),
                    "looks_ok": False,
                    "hours_work": 0
            })
        else:
            empty_users.append(user)
    
    
    
    for user in users:
        if hasattr(user, "profile"):
            have_profile = True
        else:
            have_profile = False
        all_users.append({
                    "user":user,
                    "hours_total": Session.objects.get_hours_month(user.id, month, int(year), sessions_month=user.session_set.all()),
                    "hours_unassigned": Session.objects.get_unassigned_hours_month(user.id, month, int(year), sessions_month=user.session_set.all()),
                    "hours_not_work": Session.objects.get_not_work_hours_month(user.id, month, int(year), sessions_month=user.session_set.all()),
                    "have_profile": have_profile,
                    "quota": user.profile.get_hours_quota(),
                    "months_worked": 0,
                    "this_year_holiday_aviable": 0,
                    "overall_holiday_aviable": 0,
                    "already_taken_holidays": 0,
                    "left_to_take_holidays": 0,
                    "requested_holidays": 0     
        })        

    for user in user_data:
        user["hours_work"] = user["hours_total"] - user["hours_unassigned"] - user["hours_not_work"]
        if user['hours_unassigned'] == 0 and user['hours_total'] > 0:
            user["looks_ok"] = True
        else:
            user["looks_ok"] = False
            
    for user in all_users:
        if (user["have_profile"])and(user["quota"] != 0):
            hours_work_this_year = Session.objects.get_hours_this_year(user["user"].id)
            user["hours_worked"] = user["user"].profile.get_hours_of_holidays(year = int(year)) + hours_work_this_year
            user["this_year_holiday_aviable"] = user["user"].profile.get_aviable_holidays_this_year() / user["quota"]
            user["overall_holiday_aviable"] = (user["this_year_holiday_aviable"] * user["quota"] + user["user"].profile.aviable_holidays) / user["quota"]
            user["already_taken_holidays"] = user["user"].profile.get_hours_of_holidays(year = int(year)) / user["quota"]
            user["requested_holidays"] = user["user"].profile.get_hours_of_holidays(verified = False) / user["quota"]
            user["left_to_take_holidays"] = user["user"].profile.get_hours_of_holidays_aviable_to_take() / user["quota"]

    locale.setlocale(locale.LC_ALL, "en_US.utf8")
    
    holidays = Holiday.objects.filter(
            verified = False,
    )
    context = {
            "holidays" : holidays,
            "month": month,
            "year": year,
            "user_data": sorted(user_data, key=lambda dic: (locale.strxfrm(dic["user"].last_name))),
            "empty_users": sorted(empty_users, key=lambda user: (locale.strxfrm(user.last_name))), 
            "all_users": sorted(all_users, key=lambda dic: (locale.strxfrm(dic["user"].last_name))),
    }
    return render(request, "attendance/administrator.html", context)

@login_required(login_url='/login/')
def holidays_request(request, username):
    if not user_check(request, username):
        return HttpResponse("Restricted to " + username)
       
    user = User.objects.get(username=username)
    succes = False
    if request.method == "POST":
         form = HolidayRequestForm(request.POST, user=user);
         if form.is_valid():
             succes = True
             cleaned_data = form.cleaned_data;
             Holiday.objects.create(
                        profile = user.profile,
                        date_since = cleaned_data["date_since"],
                        date_to = cleaned_data["date_to"],
                        work_hours = cleaned_data["work_hours"],
                        verified = False,
                        reason = cleaned_data["reason"]
             )
    else:
        form = HolidayRequestForm();
                
    czech_holidays_for_js = []
    for h in czech_holidays:
        czech_holidays_for_js.append([h.year, h.month, h.day])
    
    holihours_aviable = user.profile.get_hours_of_holidays_aviable_to_take()
    holidays_aviable = holihours_aviable / user.profile.get_hours_quota()
        
    context = {
        "user" : user,
        "czech_holidays" : czech_holidays_for_js,
        "quota" : user.profile.get_hours_quota(),
        "form" : form,
        "succes": succes,
        "holidays_aviable": holidays_aviable,
        "holihours_aviable": holihours_aviable
    }
           
    return render(request, "attendance/holidays_request.html", context)
    
@login_required(login_url='/login/')
def holidays_verification(request, username, id):
    if not (request.user.is_superuser or request.user.is_staff):
        return HttpResponse("Restricted to staff.")
    holidays = get_object_or_404(Holiday, pk = int(id))
    hours_on_holidays = holidays.hours_spend()
    days_on_holidays = hours_on_holidays / holidays.profile.get_hours_quota()
    check = 0
    if request.method == "POST":
        if request.POST.get("verify"):
            holidays.verified = True
            holidays.save()
            check = 1
        if request.POST.get("decline"):
            holidays.delete()
            check = 2
    context = {
            "id" : id,
            'holiday': holidays,
            "days_on_holidays": days_on_holidays,
            "hours_on_holidays": hours_on_holidays,
            "check": check
    } 
           
    return render(request, "attendance/holidays_verification.html", context)

@login_required(login_url='/login/')
def generate_pdf(request, username, year=datetime.now().year, month = datetime.now().month):
    if not user_check(request, username):
        return HttpResponse("Restricted to " + username)

    user = User.objects.get(username=username)

    in_swipes_ids = Swipe.objects.filter(
        swipe_type="IN",
        user__username=username,
        datetime__month=int(month),
        datetime__year=int(year),
    ).values_list('session', flat=True)
    sessions = Session.objects.filter(pk__in=in_swipes_ids)
    holidays = Holiday.objects.filter(profile = user.profile)
    sessions_and_holidays, days, dates = [], [], []

    for session in sessions:
        swipe_times = []
        projects = ""
        descriptions = ""
        separations =  ProjectSeparation.objects.filter(session = session)
        swipes = Swipe.objects.filter(session = session)

        for swipe in swipes:
            swipe_times.append(swipe.datetime)

        first = min(swipe_times)
        last = max(swipe_times)

        for sep in separations:
            projects += sep.project.name + "; "
            descriptions += sep.description + "; "
        sessions_and_holidays.append({
                    "date": session.get_date,
                    "day": session.get_date().day,
                    "duration": session.duration,
                    "entry": first,
                    "exit": last,
                    "projects": projects,
                    "descriptions": descriptions,
        })
    for i in range(1, monthrange(int(year),int(month))[1]+1):
        d = datetime (int(year), int(month), i)
        days.append({
            "day":i,
            "date": d,
        })

    context = {
        "user": user,
        "sessions_and_holidays": sessions_and_holidays,
        "days" : days,
        "year" : year,
        "month" : month,
        "dates" : dates,
    }

    # Rendered
    html_string = render_to_string('attendance/work_report_pdf.html', context)
    html = HTML(string=html_string)
    result = html.write_pdf()


    http_response = HttpResponse(result, content_type='attendance/work_report_pdf.html')
    http_response['Content-Disposition'] = 'filename='+user.first_name+'_'+user.last_name+'_'+year+'/'+month+'.pdf'

    return http_response
