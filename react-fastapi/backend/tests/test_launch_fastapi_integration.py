"""
setup_progress.py <-> launch_fastapi.py の連携の回帰テスト。

launch_fastapi.py を local_ai_core.launcher_kit ベースに書き直した際、
setup_progress.py 側が期待する3つのモジュール属性
(setup_progress_queue / setup_done / setup_error) の名前・型を
変えていないことを確認する。conftest.py が既定で
LAUNCH_FASTAPI_ORCHESTRATED=1 を設定しているため、`client` フィクスチャ
経由でアプリを起動すると、setup_progress.py は(開発用のダミーではなく)
実際の launch_fastapi モジュールを import する経路を通る。
"""
import queue
import threading


def test_setup_status_endpoint_reflects_launch_fastapi_module_state(client):
    import launch_fastapi as lf

    # 初期状態(まだ何もセットされていない)を確認
    resp = client.get("/api/v1/setup/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"done": lf.setup_done.is_set(), "error": lf.setup_error.is_set()}


def test_setup_progress_module_objects_have_expected_types():
    import launch_fastapi as lf

    assert isinstance(lf.setup_progress_queue, queue.Queue)
    assert isinstance(lf.setup_done, threading.Event)
    assert isinstance(lf.setup_error, threading.Event)


def test_setup_progress_router_uses_same_queue_instance_as_launch_fastapi():
    # setup_progress.py はimport時に launch_fastapi.setup_progress_queue を
    # _progress_queue に束縛する。両者が同一インスタンスであることを確認する
    # (別インスタンスだと、launcher側でpushしたログがSSEに配信されない)。
    import launch_fastapi as lf
    from api.routes import setup_progress as sp

    assert sp._progress_queue is lf.setup_progress_queue
    assert sp._done_event is lf.setup_done
    assert sp._error_event is lf.setup_error


def test_log_via_launcher_kit_reaches_setup_progress_queue():
    # launcher_kit.log() が積んだメッセージが、setup_progress.py が読む
    # キューと同じものに入ることを確認する(=SSEで実際に配信される経路)。
    import launch_fastapi as lf
    from local_ai_core import launcher_kit as lk

    # テスト間で状態が混ざらないよう、事前にキューを空にしておく
    while not lf.setup_progress_queue.empty():
        lf.setup_progress_queue.get_nowait()

    lk.log("integration check", "SUCCESS", group="test")
    item = lf.setup_progress_queue.get(timeout=1)

    assert item["message"] == "integration check"
    assert item["level"] == "SUCCESS"
    assert item["group"] == "test"
    assert "ts" in item
