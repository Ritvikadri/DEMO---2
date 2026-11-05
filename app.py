from __future__ import annotations

import calendar
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="HabitFlow — your month, in motion", page_icon="✳️", layout="wide", initial_sidebar_state="expanded")

DATA_PATH = Path(__file__).parent / "data.json"
with DATA_PATH.open(encoding="utf-8") as fp:
    SEED = json.load(fp)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');
:root{--ink:#eef2f7;--muted:#8794a7;--bg:#0c1118;--panel:#121a24;--line:#202b38;--mint:#98f6c3;--violet:#b5a4ff}
html,body,[class*="css"]{font-family:'Manrope',sans-serif} .stApp{background:radial-gradient(ellipse at 88% 2%,#182736 0,transparent 38%),var(--bg);color:var(--ink)}
[data-testid="stSidebar"]{background:#0b1016;border-right:1px solid var(--line)} [data-testid="stSidebar"] *{color:var(--ink)}
h1,h2,h3{letter-spacing:-.045em} h1{font-size:2.5rem!important;font-weight:800!important} p,.muted{color:var(--muted)}
.eyebrow{font:500 11px 'DM Mono',monospace;letter-spacing:.16em;text-transform:uppercase;color:var(--mint)}
.hero{padding:22px 0 16px}.hero h1{margin:8px 0 4px}.hero p{margin:0;color:var(--muted)}
.card{background:linear-gradient(145deg,#151f2a,#111821);border:1px solid var(--line);border-radius:18px;padding:20px 22px;height:100%;box-shadow:0 16px 48px #0002}
.metric-label{font:500 10px 'DM Mono',monospace;text-transform:uppercase;letter-spacing:.14em;color:var(--muted)} .metric-value{font-size:2rem;font-weight:800;letter-spacing:-.06em;margin:7px 0 2px}.metric-note{font-size:12px;color:var(--muted)}
.section-title{font-weight:800;letter-spacing:-.04em;font-size:1.3rem;margin:22px 0 12px}.habit-name{font-weight:700}.streak{font:11px 'DM Mono',monospace;color:var(--muted)}
.pill{border:1px solid var(--line);border-radius:999px;padding:7px 11px;color:var(--muted);font:11px 'DM Mono',monospace}
div.stButton>button{border-radius:12px;border:1px solid #2b3b4a;background:#15212c;color:var(--ink);font-weight:700;transition:.18s ease}div.stButton>button:hover{border-color:var(--mint);color:var(--mint);transform:translateY(-1px)}
div[data-testid="stMetric"]{background:linear-gradient(145deg,#151f2a,#111821);border:1px solid var(--line);padding:18px 20px;border-radius:17px}div[data-testid="stMetricLabel"]{color:var(--muted)} div[data-testid="stMetricValue"]{color:var(--ink)}
div[data-testid="stProgress"]>div>div{background:linear-gradient(90deg,var(--mint),#75d9ed)}
.block-container{padding-top:2rem;padding-bottom:3rem;max-width:1440px}
button[kind="primary"]{background:var(--mint);color:#0c1711;border-color:var(--mint)}
</style>
""", unsafe_allow_html=True)


def supabase_client():
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_ANON_KEY", "")
    try:
        url = url or st.secrets.get("SUPABASE_URL", "")
        key = key or st.secrets.get("SUPABASE_ANON_KEY", "")
    except Exception:
        pass
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception as exc:
        st.error(f"Supabase setup issue: {exc}")
        return None


@st.cache_resource
def client():
    return supabase_client()


def seed_state():
    return {h['name']: dict(h) for h in SEED['habits']}


def load_state():
    if 'habits' not in st.session_state:
        st.session_state.habits = seed_state()
    sb = client()
    user = st.session_state.get('user')
    if sb and user and not st.session_state.get('loaded_remote'):
        try:
            result = sb.table('habit_data').select('payload').eq('user_id', str(user.id)).limit(1).execute()
            if result.data:
                payload = result.data[0]['payload']
                st.session_state.habits = {h['name']: h for h in payload.get('habits', [])}
                st.session_state.loaded_remote = True
        except Exception as exc:
            st.warning(f"Could not load saved habits: {exc}")


def persist():
    sb, user = client(), st.session_state.get('user')
    if not sb or not user:
        return
    try:
        sb.table('habit_data').upsert({'user_id': str(user.id), 'payload': {'habits': list(st.session_state.habits.values())}}, on_conflict='user_id').execute()
    except Exception as exc:
        st.warning(f"Your change is on this device, but could not sync to Supabase: {exc}")


def auth_screen():
    st.markdown('<div style="height:8vh"></div>', unsafe_allow_html=True)
    left, mid, right = st.columns([1, 1.15, 1])
    with mid:
        st.markdown('<div class="eyebrow">✳ HabitFlow · personal dashboard</div>', unsafe_allow_html=True)
        st.title('Make consistency\nfeel effortless.')
        st.write('Your habits, goals, streaks and daily rhythm — in one clear place.')
        sb = client()
        if sb is None:
            st.info('Add your Supabase URL and anon key in `.streamlit/secrets.toml` or environment variables to enable secure login and cloud sync. The demo dashboard is available below.')
            with st.form('demo'):
                st.text_input('Email', placeholder='you@example.com')
                st.form_submit_button('Continue with demo', type='primary', use_container_width=True)
            if st.button('Open interactive preview', use_container_width=True):
                st.session_state.user = None
                st.session_state.preview = True
                st.rerun()
            return
        mode = st.segmented_control('Account', ['Sign in', 'Create account'], default='Sign in', label_visibility='collapsed')
        with st.form('auth'):
            email = st.text_input('Email', placeholder='you@example.com')
            password = st.text_input('Password', type='password', placeholder='At least 8 characters')
            submit = st.form_submit_button(mode or 'Sign in', type='primary', use_container_width=True)
        if submit:
            try:
                response = sb.auth.sign_in_with_password({'email': email, 'password': password}) if mode == 'Sign in' else sb.auth.sign_up({'email': email, 'password': password})
                if response.user:
                    st.session_state.user = response.user
                    st.session_state.loaded_remote = False
                    st.rerun()
                st.success('Check your email to finish creating your account.')
            except Exception as exc:
                st.error(f"Couldn't authenticate: {exc}")
        if st.button('Preview the dashboard', use_container_width=True):
            st.session_state.user = None
            st.session_state.preview = True
            st.rerun()


def month_days(year, month):
    return [date(year, month, d) for d in range(1, calendar.monthrange(year, month)[1] + 1)]


def calc_streak(checks, today):
    run = 0
    day = today
    while checks.get(day.isoformat(), False):
        run += 1
        day -= timedelta(days=1)
    values = sorted((date.fromisoformat(k), bool(v)) for k, v in checks.items())
    best = run_best = 0
    prev = None
    for d, done in values:
        if done:
            if prev and (d - prev).days == 1:
                best += 1
            else:
                best = 1
            run_best = max(run_best, best)
            prev = d
        else:
            best = 0
            prev = None
    return run, run_best


def dashboard():
    load_state()
    if 'year' not in st.session_state:
        st.session_state.year, st.session_state.month = SEED.get('year') or date.today().year, 11
    year, month = st.session_state.year, st.session_state.month
    days = month_days(year, month)
    today = date.today()
    habits = st.session_state.habits
    total = len(habits)
    completed = sum(bool(h['checks'].get(d.isoformat())) for h in habits.values() for d in days)
    possible = total * len(days)
    rate = round(completed / possible * 100) if possible else 0
    today_done = sum(bool(h['checks'].get(today.isoformat())) for h in habits.values())
    week_start = today - timedelta(days=today.weekday())
    week_dates = [week_start + timedelta(days=i) for i in range(7)]
    week_done = sum(bool(h['checks'].get(d.isoformat())) for h in habits.values() for d in week_dates)
    week_total = total * 7

    with st.sidebar:
        st.markdown('<div class="eyebrow">✳ HABITFLOW</div>', unsafe_allow_html=True)
        st.markdown('## Your space')
        page = st.radio('Navigate', ['Overview', 'Habit board', 'Insights', 'Manage habits'], label_visibility='collapsed')
        st.markdown('---')
        st.caption('YOUR TRACKING PERIOD')
        sel_month = st.selectbox('Month', list(range(1, 13)), index=month - 1, format_func=lambda x: calendar.month_name[x])
        sel_year = st.number_input('Year', min_value=2020, max_value=2040, value=year, step=1)
        if sel_month != month or sel_year != year:
            st.session_state.month, st.session_state.year = sel_month, sel_year
            st.rerun()
        st.markdown('---')
        if st.session_state.get('user'):
            st.caption(st.session_state.user.email)
            if st.button('Sign out', use_container_width=True):
                try: client().auth.sign_out()
                except Exception: pass
                st.session_state.clear(); st.rerun()
        else:
            st.caption('Preview mode · changes stay local')
            if st.button('Sign in / create account', use_container_width=True):
                st.session_state.preview = False; st.rerun()

    date_label = f"{today.strftime('%A')} · {calendar.month_name[today.month]} {today.day}, {today.year}"
    title = "Your habits, in motion." if page == "Overview" else page
    st.markdown(f'<div class="hero"><div class="eyebrow">{date_label}</div><h1>{title}</h1><p>Small actions. Real momentum. Here\'s your {calendar.month_name[month]} at a glance.</p></div>', unsafe_allow_html=True)
    if page == 'Overview':
        c1,c2,c3,c4=st.columns(4)
        c1.metric('TODAY', f'{today_done} / {total}', 'habits completed')
        c2.metric('MONTHLY PROGRESS', f'{rate}%', f'{completed} completed check-ins')
        c3.metric('THIS WEEK', f'{round(week_done/week_total*100) if week_total else 0}%', 'weekly rhythm')
        c4.metric('ACTIVE HABITS', total, 'building your routine')
        st.markdown('<div class="section-title">Your daily rhythm</div>',unsafe_allow_html=True)
        st.progress(today_done/total if total else 0, text=f'{today_done} of {total} habits checked off today')
        st.markdown('<div class="section-title">The month at a glance</div>',unsafe_allow_html=True)
        for chunk_start in range(0, len(days), 7):
            cols=st.columns(min(7,len(days)-chunk_start))
            for col,d in zip(cols,days[chunk_start:chunk_start+7]):
                count=sum(bool(h['checks'].get(d.isoformat())) for h in habits.values())
                pct=count/total if total else 0
                col.markdown(f'<div class="card" style="padding:11px 8px;text-align:center"><div class="metric-label">{d.strftime("%a")}</div><div style="font-weight:800;font-size:20px;margin:5px">{d.day}</div><div style="height:5px;border-radius:5px;background:#253140"><div style="height:5px;width:{pct*100}%;border-radius:5px;background:linear-gradient(90deg,#98f6c3,#75d9ed)"></div></div><div class="metric-note" style="margin-top:6px">{count}/{total}</div></div>',unsafe_allow_html=True)
        a,b=st.columns([1.4,1])
        with a:
            st.markdown('<div class="section-title">This week</div>',unsafe_allow_html=True)
            df=pd.DataFrame({'Day':[d.strftime('%a %d') for d in week_dates], 'Completed':[sum(bool(h['checks'].get(d.isoformat())) for h in habits.values()) for d in week_dates]})
            st.bar_chart(df.set_index('Day'), color='#98f6c3', height=220)
        with b:
            st.markdown('<div class="section-title">Top 5 this month</div>',unsafe_allow_html=True)
            ranked=sorted(habits.values(),key=lambda h:sum(bool(h['checks'].get(d.isoformat())) for d in days),reverse=True)[:5]
            for i,h in enumerate(ranked,1):
                n=sum(bool(h['checks'].get(d.isoformat())) for d in days)
                st.markdown(f'<div class="card" style="padding:12px 15px;margin-bottom:8px"><span class="eyebrow">0{i}</span> &nbsp; <b>{h["name"]}</b><span style="float:right;color:#98f6c3">{n} days</span></div>',unsafe_allow_html=True)
        st.markdown('<div class="section-title">A little nudge</div>',unsafe_allow_html=True)
        pending=[h['name'] for h in habits.values() if not h['checks'].get(today.isoformat())]
        st.info(('You have a clean slate: '+', '.join(pending[:4])+('…' if len(pending)>4 else '')) if pending else 'Beautiful work — today’s habits are all checked off. Take a moment to celebrate.')

    elif page == 'Habit board':
        st.markdown('<div class="section-title">Tap a day to update it · scroll horizontally for the full month</div>',unsafe_allow_html=True)
        for name,h in list(habits.items()):
            done=sum(bool(h['checks'].get(d.isoformat())) for d in days)
            streak,best=calc_streak(h['checks'],today)
            with st.container(border=True):
                head,goal,progress=st.columns([2,1,1])
                head.markdown(f'**{name}**  &nbsp; <span class="streak">🔥 {streak} day streak · best {best}</span>',unsafe_allow_html=True)
                goal.caption(f"Goal · {h.get('goal') or '—'} days")
                progress.caption(f'{done} / {len(days)} · {round(done/len(days)*100)}%')
                cols=st.columns(len(days))
                for col,d in zip(cols,days):
                    key=f"check_{name}_{d.isoformat()}"
                    checked=bool(h['checks'].get(d.isoformat()))
                    with col:
                        val=st.checkbox(d.strftime('%d'),value=checked,key=key,help=d.strftime('%A, %B %d'))
                    if val != checked:
                        h['checks'][d.isoformat()]=val
                        persist()
                        st.rerun()
        st.markdown('<div class="section-title">Monthly check-in heatmap</div>',unsafe_allow_html=True)
        heat=pd.DataFrame({d.strftime('%b %d'):[int(bool(h['checks'].get(d.isoformat()))) for h in habits.values()] for d in days},index=list(habits.keys()))
        st.dataframe(heat.style.background_gradient(cmap='Greens',axis=None),use_container_width=True,height=420)

    elif page == 'Insights':
        st.markdown('<div class="section-title">Progress that adds up</div>',unsafe_allow_html=True)
        ranking=[]
        for name,h in habits.items():
            n=sum(bool(h['checks'].get(d.isoformat())) for d in days)
            streak,best=calc_streak(h['checks'],today)
            ranking.append({'Habit':name,'Completed':n,'Goal':h.get('goal') or 0,'Completion':round(n/len(days)*100),'Current streak':streak,'Best streak':best})
        df=pd.DataFrame(ranking).sort_values('Completed',ascending=False)
        a,b=st.columns(2)
        with a: st.markdown('<div class="section-title">Completions by habit</div>',unsafe_allow_html=True); st.bar_chart(df.set_index('Habit')[['Completed']],color='#98f6c3')
        with b:
            st.markdown('<div class="section-title">Weekly overview</div>',unsafe_allow_html=True)
            weekrows=[]
            for w in range(5):
                subset=days[w*7:(w+1)*7]
                done=sum(bool(h['checks'].get(d.isoformat())) for h in habits.values() for d in subset)
                weekrows.append({'Week':f'Week {w+1}','Completed':done,'Possible':len(subset)*total})
            st.bar_chart(pd.DataFrame(weekrows).set_index('Week'),color=['#98f6c3','#354252'])
        st.markdown('<div class="section-title">Streaks & goals</div>',unsafe_allow_html=True)
        st.dataframe(df[['Habit','Completed','Goal','Completion','Current streak','Best streak']],use_container_width=True,hide_index=True)

    else:
        st.markdown('<div class="section-title">Build a routine that fits you</div>',unsafe_allow_html=True)
        with st.form('add_habit',clear_on_submit=True):
            name=st.text_input('Habit name',placeholder='e.g. Journal for 10 minutes')
            goal=st.number_input('Monthly goal (days)',1,len(days),min(20,len(days)))
            added=st.form_submit_button('＋ Add this habit',type='primary')
        if added and name.strip():
            if name.strip() in habits: st.warning('That habit is already in your list.')
            else:
                habits[name.strip()]={'name':name.strip(),'goal':int(goal),'checks':{}}
                persist(); st.success(f'Added {name.strip()}'); st.rerun()
        st.markdown('<div class="section-title">Your habits</div>',unsafe_allow_html=True)
        for name,h in list(habits.items()):
            with st.container(border=True):
                c1,c2,c3=st.columns([4,2,1])
                c1.markdown(f'**{name}**')
                c2.write(f"Goal · {h.get('goal') or '—'} days")
                if c3.button('Remove',key='remove_'+name):
                    del habits[name]; persist(); st.rerun()
        st.caption('Removing a habit also removes its check-in history from this account.')


if st.session_state.get('user') or st.session_state.get('preview'):
    dashboard()
else:
    auth_screen()
