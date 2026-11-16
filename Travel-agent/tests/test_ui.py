from pathlib import Path
from streamlit.testing.v1 import AppTest

def test_homepage_chat_and_new_conversation():
    app=AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py').run(timeout=20)
    assert not app.exception
    assert app.title[0].value=='Find a stay that feels like you.'
    app.button(key="start_planning").click().run()
    assert not app.exception and app.chat_input
    assert app.title[0].value=='Let’s find your place.'
    app.button(key="reset_chat").click().run()
    assert not app.exception
    assert app.session_state['conversation'].history==[]

def test_missing_provider_error_keeps_conversation(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','ollama')
    monkeypatch.setenv('OLLAMA_BASE_URL','http://127.0.0.1:1')
    monkeypatch.setenv('EMBEDDING_MODEL','')
    app=AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py').run(timeout=20)
    app.button(key="start_planning").click().run()
    app.chat_input[0].set_value('I would like a hotel in Dubai').run(timeout=30)
    assert not app.exception
    assert app.error and 'temporarily unavailable' in app.error[0].value
    assert not app.session_state['conversation'].history

def test_inspiration_prefills_without_model_calls():
    app=AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py').run(timeout=20)
    app.button(key='coastal_idea').click().run()
    assert not app.exception and not app.error
    assert app.session_state['started']
    assert app.chat_input[0].value=="I'd like a stay near the sea. Help me choose a destination."
    assert app.session_state['conversation'].history==[]


def test_return_to_discover_preserves_conversation_and_reset_clears_it():
    from travel_agent.models import Session
    app=AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py').run(timeout=20)
    app.session_state['conversation']=Session(history=[{'role':'user','content':'A trip to Japan'},
        {'role':'assistant','content':'Where in Japan would you like to explore?'}],slots={'country':'Japan'})
    app.button(key='start_planning').click().run()
    assert len(app.chat_message)==2
    app.button(key='back_home').click().run()
    assert len(app.session_state['conversation'].history)==2
    app.button(key='start_planning').click().run()
    assert len(app.chat_message)==2
    app.button(key='reset_chat').click().run()
    assert not app.session_state['conversation'].history and not app.session_state['conversation'].slots


def test_trip_summary_escapes_user_content():
    from travel_agent.models import Session
    app=AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py').run(timeout=20)
    app.session_state['conversation']=Session(slots={'city':'<script>alert(1)</script>'})
    app.button(key='start_planning').click().run()
    assert not app.exception
    html_blocks=[item.value for item in app.markdown if 'trip-item' in item.value]
    assert any('&lt;script&gt;' in block for block in html_blocks)
    assert not any('<script>alert(1)</script>' in block for block in html_blocks)
