from __future__ import annotations

from sqlalchemy import func, select

from app.models import Draft, FollowUp, Mailbox, Message, Thread, User
from conftest import compose


def get_thread(app, thread_id):
    with app.state.sessionmaker() as db:
        return db.get(Thread, thread_id)


def test_priority_inbox_puts_a_vip_question_first(browser, app):
    with app.state.sessionmaker() as db:
        uid = db.scalar(select(User.id).where(User.email == "swayam@example.com"))
        user = db.get(User, uid)
        user.vips = "priya@lumen.example"
        db.commit()
    compose(browser, subject="Bulk note", sender="news@x.example", body="Unsubscribe from this newsletter.")
    compose(browser, subject="VIP ask", sender="Priya <priya@lumen.example>", body="Can you confirm the date?")
    page = browser.get("/inbox?view=priority").text
    assert page.index("VIP ask") < page.index("Bulk note")
    assert "VIP sender" in page


def test_inbox_defaults_to_priority_and_hides_closed(browser):
    open_id = compose(browser, subject="Still open")
    closed_id = compose(browser, subject="Will close")
    browser.post(f"/threads/{closed_id}/status", {"status": "closed", "next": f"/threads/{closed_id}"})
    page = browser.get("/inbox").text
    assert "Still open" in page
    assert "Will close" not in page
    assert "Priority" in page


def test_the_closed_view_lists_closed_threads(browser):
    thread_id = compose(browser, subject="Filed away")
    browser.post(f"/threads/{thread_id}/status", {"status": "closed", "next": "/inbox"})
    page = browser.get("/inbox?view=closed").text
    assert "Filed away" in page
    assert "Closed" in page


def test_category_views_filter_the_list(browser):
    compose(browser, subject="A question", body="Can you confirm by Friday?")
    compose(browser, subject="A receipt", sender="billing@x.example", body="Your invoice. Total charged: 20 USD.")
    reply = browser.get("/inbox?view=reply").text
    receipt = browser.get("/inbox?view=receipt").text
    assert "A question" in reply and "A receipt" not in reply
    assert "A receipt" in receipt and "A question" not in receipt


def test_starred_view(browser):
    thread_id = compose(browser, subject="Star me")
    browser.post(f"/threads/{thread_id}/star", {"next": "/inbox"})
    page = browser.get("/inbox?view=starred").text
    assert "Star me" in page


def test_search_matches_the_subject(browser):
    compose(browser, subject="Launch checklist")
    compose(browser, subject="Something else", body="Nothing to see.")
    page = browser.get("/inbox?q=checklist").text
    assert "Launch checklist" in page
    assert "Something else" not in page


def test_search_matches_the_body(browser):
    compose(browser, subject="Body match", body="The secret word is platypus.")
    compose(browser, subject="Other", body="No animals here.")
    assert "Body match" in browser.get("/inbox?q=platypus").text


def test_search_matches_a_participant(browser):
    compose(browser, subject="From Priya", sender="Priya Raman <priya@lumen.example>")
    page = browser.get("/inbox?q=priya").text
    assert "From Priya" in page


def test_search_treats_a_percent_as_a_literal(browser):
    compose(browser, subject="100% done")
    compose(browser, subject="100x done")
    page = browser.get("/inbox?q=100%25").text
    assert "100% done" in page
    assert "100x done" not in page


def test_search_with_no_match_shows_an_empty_state(browser):
    compose(browser, subject="Hello")
    page = browser.get("/inbox?q=nothingmatches").text
    assert "No matches" in page


def test_mailbox_filter(browser, app):
    compose(browser, subject="In personal")
    with app.state.sessionmaker() as db:
        uid = db.scalar(select(User.id).where(User.email == "swayam@example.com"))
        work = Mailbox(user_id=uid, name="Work", address="work@example.com")
        db.add(work)
        db.commit()
        work_id = work.id
    compose(browser, subject="In work", mailbox_id=str(work_id), body="Different box.")
    page = browser.get(f"/inbox?mailbox={work_id}").text
    assert "In work" in page
    assert "In personal" not in page


def test_an_unknown_view_falls_back_to_priority(browser):
    compose(browser, subject="Visible anywhere")
    page = browser.get("/inbox?view=not-a-view").text
    assert "Visible anywhere" in page


def test_route_can_be_changed_and_records_the_source(browser, app):
    thread_id = compose(browser)
    r = browser.post(f"/threads/{thread_id}/category", {"category": "fyi", "next": f"/threads/{thread_id}"})
    assert r.status_code == 303
    thread = get_thread(app, thread_id)
    assert thread.category == "fyi"
    assert thread.category_source == "you"
    assert "FYI" in browser.get(f"/threads/{thread_id}").text


def test_an_unknown_category_is_rejected(browser, app):
    thread_id = compose(browser)
    r = browser.post(f"/threads/{thread_id}/category", {"category": "urgent-ish", "next": "/inbox"})
    assert r.status_code == 422


def test_the_next_parameter_cannot_leave_the_site(browser):
    thread_id = compose(browser)
    r = browser.post(
        f"/threads/{thread_id}/star", {"next": "https://evil.example/phish"}
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"/threads/{thread_id}"


def test_star_toggles_both_ways(browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/star", {"next": "/inbox"})
    assert get_thread(app, thread_id).starred is True
    browser.post(f"/threads/{thread_id}/star", {"next": "/inbox"})
    assert get_thread(app, thread_id).starred is False


def test_mark_unread_sets_the_flag_and_redirects_to_inbox(browser, app):
    thread_id = compose(browser)
    browser.get(f"/threads/{thread_id}")
    assert get_thread(app, thread_id).unread is False
    r = browser.post(f"/threads/{thread_id}/unread", {"next": "/inbox"})
    assert r.headers["location"] == "/inbox"
    assert get_thread(app, thread_id).unread is True


def test_status_can_be_set_to_waiting(browser, app):
    thread_id = compose(browser)
    r = browser.post(f"/threads/{thread_id}/status", {"status": "waiting", "next": "/inbox"})
    assert r.status_code == 303
    assert get_thread(app, thread_id).status == "waiting"
    assert "Waiting on them" in browser.get("/inbox").text


def test_an_unknown_status_is_rejected(browser):
    thread_id = compose(browser)
    r = browser.post(f"/threads/{thread_id}/status", {"status": "sideways", "next": "/inbox"})
    assert r.status_code == 422


def test_deleting_a_thread_removes_its_children(browser, app):
    thread_id = compose(browser)
    browser.post(f"/threads/{thread_id}/followups", {"title": "Waiting on the deck"})
    browser.post(f"/threads/{thread_id}/draft", {"tone": "brief", "engine": "local"})
    r = browser.post(f"/threads/{thread_id}/delete")
    assert r.status_code == 303
    assert r.headers["location"] == "/inbox"
    with app.state.sessionmaker() as db:
        assert db.get(Thread, thread_id) is None
        assert db.scalar(select(func.count(Message.id)).where(Message.thread_id == thread_id)) == 0
        assert db.scalar(select(func.count(Draft.id)).where(Draft.thread_id == thread_id)) == 0
        assert db.scalar(select(func.count(FollowUp.id)).where(FollowUp.thread_id == thread_id)) == 0


def test_a_second_user_cannot_delete_the_first_users_thread(browser, make_browser, app):
    thread_id = compose(browser)
    other = make_browser().register(email="other@example.com", name="Other")
    other.get("/inbox")
    r = other.post(f"/threads/{thread_id}/delete")
    assert r.status_code == 404
    assert get_thread(app, thread_id) is not None


def test_thread_detail_shows_the_conversation_and_the_score(browser):
    thread_id = compose(browser, body="Can you confirm the launch date by Friday?")
    page = browser.get(f"/threads/{thread_id}").text
    assert "Can you confirm the launch date" in page
    assert "Why this rank" in page
    assert "/ 100" in page
    assert "Mentions a deadline" in page
    assert "Local" in page


def test_re_summarise_keeps_the_local_label(browser, app):
    thread_id = compose(browser)
    r = browser.post(f"/threads/{thread_id}/summarize")
    assert r.status_code == 303
    assert get_thread(app, thread_id).summary_source == "local"
    assert "no model call" in browser.get(f"/threads/{thread_id}").text


def test_a_thread_from_another_account_is_a_404(browser, make_browser):
    thread_id = compose(browser)
    other = make_browser().register(email="other@example.com", name="Other")
    assert other.get(f"/threads/{thread_id}").status_code == 404


def test_inbox_rows_show_the_mailbox_and_message_count(browser):
    compose(browser, subject="Counted")
    page = browser.get("/inbox").text
    assert "Personal" in page
    assert "1 message" in page


def test_csrf_is_required_for_a_state_change(browser, app):
    thread_id = compose(browser)
    r = browser.post(f"/threads/{thread_id}/star", {"next": "/inbox"}, csrf=False)
    assert r.status_code == 403
    assert get_thread(app, thread_id).starred is False


def test_the_dashboard_shows_priority_rows_and_counts(browser):
    compose(browser, subject="On the desk")
    page = browser.get("/").text
    assert "On the desk" in page
    assert "Priority inbox" in page
    assert "Needs reply" in page
    assert "Good " in page
