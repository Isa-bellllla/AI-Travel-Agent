"""Stillwater's consumer interface. Model and database logic live in travel_agent/."""
import base64
import html
from pathlib import Path
from dotenv import load_dotenv
import streamlit as st
from travel_agent.data import Database
from travel_agent.models import Session
from travel_agent.llm import JsonLLM, ModelUnavailable
from travel_agent.retrieval import HybridIndex
from travel_agent.agent import Agent

ROOT=Path(__file__).resolve().parent
load_dotenv(ROOT/'.env', override=False)
st.set_page_config(page_title='Stillwater • Find your kind of elsewhere',page_icon='🌊',layout='wide')
st.markdown('<style>'+(ROOT/'assets/style.css').read_text()+'</style>',unsafe_allow_html=True)

@st.cache_data
def image_uri(name):
    return 'data:image/png;base64,'+base64.b64encode((ROOT/'assets'/name).read_bytes()).decode()

@st.cache_resource
def database(): return Database()

@st.cache_resource
def services():
    db=database(); provider=JsonLLM()
    return Agent(db,HybridIndex(db,provider),provider)


def begin():
    st.session_state.started=True


def use_idea(text):
    st.session_state.started=True
    st.session_state.travel_message=text


def reset_conversation():
    st.session_state.conversation=Session()
    st.session_state.travel_message=''


def go_home():
    st.session_state.started=False


def nav():
    st.markdown('''<nav class="brand-nav" aria-label="Stillwater">
      <div class="brand"><span class="brand-mark" aria-hidden="true">✷</span> stillwater</div>
      <div class="nav-note">Find your kind<br>of elsewhere.</div>
    </nav>''',unsafe_allow_html=True)


def footer():
    st.markdown('''<footer class="footer"><span>STILLWATER · A more personal way to get away.</span>
      <span>Reference prices in USD/night. Live rates and availability are not provided.<br>
      Travel imagery is AI-generated inspiration, not photographs of recommended hotels.</span></footer>''',unsafe_allow_html=True)


def trip_notes(state):
    s=html.escape
    with st.container(key='trip_notes'):
        st.markdown(f'<div class="chat-banner"><img src="{image_uri("coast.png")}" alt="Illustrative sunlit coast and turquoise sea"></div>',unsafe_allow_html=True)
        st.markdown('<div class="trip-kicker">A little space to dream</div><div class="trip-heading">Your trip, taking shape.</div>',unsafe_allow_html=True)
        entries=[]
        destination=', '.join(str(state.slots[k]) for k in ('city','country') if state.slots.get(k))
        if destination: entries.append(('Destination',destination))
        if state.slots.get('category'): entries.append(('Hotel style',str(state.slots['category'])))
        if state.slots.get('brand'): entries.append(('Preferred brand',str(state.slots['brand'])))
        budget=state.slots.get('max_budget')
        if budget:
            label='Up to' if state.slots.get('budget_hard',True) else 'Around'
            entries.append(('Reference budget',f'{label} USD {budget:,.0f} / night'))
        for pref in list(state.preferences.values())[:4]:
            if pref.confirmed: entries.append(('Your priorities',('Avoid: ' if pref.negated else '')+pref.value))
        if entries:
            markup=''.join(f'<div class="trip-item"><small>{s(label)}</small><span>{s(value)}</span></div>' for label,value in entries)
            st.markdown(markup,unsafe_allow_html=True)
            st.markdown('<p class="trip-note">Change your mind as you go. Just tell me what matters more.</p>',unsafe_allow_html=True)
        else:
            st.markdown('<p class="trip-note">A destination, a feeling, a little wish list. We’ll bring the details together as we talk.</p>',unsafe_allow_html=True)
        st.markdown('<p class="trip-note">Illustrative travel imagery.</p>',unsafe_allow_html=True)


if 'conversation' not in st.session_state: st.session_state.conversation=Session()
if 'started' not in st.session_state: st.session_state.started=False
nav()

if not st.session_state.started:
    left,right=st.columns([1,1.24],gap='large',vertical_alignment='center')
    with left:
        st.markdown('<div class="eyebrow">For the places you haven’t been. Yet.</div>',unsafe_allow_html=True)
        st.title('Find a stay that feels like you.')
        st.markdown('<p class="hero-description">A slower morning. A new favorite city. A little more sea and a little less routine.<br>Let’s find the stay that starts it all.</p>',unsafe_allow_html=True)
        st.button('Start Planning Your Trip',type='primary',key='start_planning',on_click=begin)
        st.markdown('<div class="microcopy">Start with a place. Or just a feeling. ↗</div>',unsafe_allow_html=True)
    with right:
        st.markdown(f'''<div class="hero-photo"><img src="{image_uri('coast.png')}"
            alt="Illustrative Mediterranean-style turquoise bay, stone path and bougainvillea">
            <div class="photo-stamp"><div><small>Your next chapter</small><br><b>A little closer to elsewhere.</b></div><span class="stamp-arrow" aria-hidden="true">↗</span></div>
            </div><div class="photo-credit">A scene to dream about · Illustrative travel imagery</div>''',unsafe_allow_html=True)
    db=database()
    countries=len({r['country'] for r in db.records.values()})
    st.markdown(f'''<div class="stats-strip">
      <div class="stat"><strong>{len(db.records):,}</strong><span>HOTELS TO EXPLORE</span></div>
      <div class="stat"><strong>{countries}</strong><span>COUNTRIES, COUNTLESS POSSIBILITIES</span></div>
      <div class="stat"><strong>Less searching. More imagining.</strong><span>A conversation built around your kind of trip.</span></div>
    </div>''',unsafe_allow_html=True)
    st.markdown('<div class="section-header" id="find-your-escape"><h2>What are you dreaming of?</h2><p>A feeling is a good place to start.</p></div>',unsafe_allow_html=True)
    coast,culture=st.columns(2,gap='large')
    with coast:
        st.markdown(f'''<article class="mood-card"><img src="{image_uri('coast.png')}" alt="Illustrative coastal escape">
          <div class="mood-caption"><b>Out of office. Into the blue.</b><span>The slow escape</span></div>
          <p class="mood-copy">Salt air, unhurried days, and room to breathe. Find your version of a seaside stay.</p></article>''',unsafe_allow_html=True)
        st.button('Find my coastal escape ↗',key='coastal_idea',on_click=use_idea,
                  args=("I'd like a stay near the sea. Help me choose a destination.",))
    with culture:
        st.markdown(f'''<article class="mood-card"><img src="{image_uri('culture.png')}" alt="Illustrative Japanese-style lane with spring flowers and timber architecture">
          <div class="mood-caption"><b>Take the scenic way.</b><span>The curious escape</span></div>
          <p class="mood-copy">New streets, small discoveries, and a place worth coming back to at the end of the day.</p></article>''',unsafe_allow_html=True)
        st.button('Explore a different pace ↗',key='culture_idea',on_click=use_idea,
                  args=("I'd like to explore Japan. Help me find a hotel that suits my trip.",))
    st.markdown('''<div class="promise-strip">
      <div><span>01 / TELL US YOUR KIND OF TRIP</span><h3>There’s no one way to get away.</h3><p>Start with what matters to you. We’ll ask a little, listen closely, and explore together.</p></div>
      <div><span>02 / FIND YOUR SHORTLIST</span><h3>Good reasons. Thoughtful choices.</h3><p>Compare stays with recorded details, reference prices, and clear reasons for each recommendation.</p></div>
      <div><span>03 / MAKE IT YOURS</span><h3>Keep the conversation going.</h3><p>More beach? A different budget? A new destination? Your plans can change as you talk.</p></div>
    </div>''',unsafe_allow_html=True)
    footer()
else:
    with st.container(key='chat_toolbar'):
        toolbar_left,toolbar_right=st.columns([3,1],gap='small')
        with toolbar_left:
            st.button('← Discover',key='back_home',on_click=go_home)
        with toolbar_right:
            st.button('New Conversation',key='reset_chat',on_click=reset_conversation)
    main,aside=st.columns([3.1,1.05],gap='large')
    state=st.session_state.conversation
    with main:
        st.markdown('<div class="eyebrow">Your personal travel companion</div>',unsafe_allow_html=True)
        st.title('Let’s find your place.')
        st.markdown('<p class="chat-intro">Tell me what a great stay looks like for you. We’ll take it from there.</p>',unsafe_allow_html=True)
        if not state.history:
            st.info('Where would you like to go, or what kind of escape are you imagining?')
            st.caption('A few ways to begin — choose one to put it in the message box.')
            st.button('A luxury stay in Dubai ↗',key='dubai_idea',on_click=use_idea,
                      args=('I would like a luxury hotel in Dubai.',))
            st.button('Somewhere near the sea ↗',key='sea_idea',on_click=use_idea,
                      args=("I'd like a stay near the sea. Help me choose a destination.",))
        for item in state.history:
            with st.chat_message(item['role'],avatar='🌊' if item['role']=='assistant' else None):
                st.markdown(item['content'])
    with aside:
        trip_notes(state)
    st.caption('Reference prices in USD/night. Live rates and availability are not provided. You can change your preferences at any time.')
    prompt=st.chat_input('A place, a feeling, a wish list…',max_chars=12000,key='travel_message')
    if prompt:
        with main:
            with st.spinner('Finding the possibilities. Checking the details…'):
                try:
                    services().respond(prompt,state)
                except ModelUnavailable:
                    st.error('Your travel consultant is temporarily unavailable. Please try again after the service is restored. Your conversation has been kept.')
                except ValueError as exc:
                    st.warning(str(exc))
                except Exception:
                    st.error('We couldn’t complete that search. Your conversation has been kept; please try again.')
                else:
                    st.rerun()
