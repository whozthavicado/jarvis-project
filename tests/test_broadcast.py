"""Broadcaster pub/sub tests — pure asyncio, no real WebSocket involved."""
import asyncio

from jarvis.core.broadcast import Broadcaster


async def test_publish_reaches_all_subscribers():
    b = Broadcaster()
    q1 = b.subscribe()
    q2 = b.subscribe()

    b.publish({"type": "status", "state": "idle"})

    assert q1.get_nowait() == {"type": "status", "state": "idle"}
    assert q2.get_nowait() == {"type": "status", "state": "idle"}


async def test_unsubscribed_queue_receives_nothing():
    b = Broadcaster()
    q = b.subscribe()
    b.unsubscribe(q)

    b.publish({"type": "status", "state": "idle"})

    assert q.qsize() == 0


async def test_a_slow_full_subscriber_does_not_block_others():
    b = Broadcaster(maxsize=2)
    slow = b.subscribe()
    fast = b.subscribe()

    for i in range(5):  # more than maxsize -- must not raise or block
        b.publish({"n": i})

    assert fast.qsize() == 2
    assert slow.qsize() == 2
    # drop-oldest: the slow queue should hold the two most recent events
    assert slow.get_nowait() == {"n": 3}
    assert slow.get_nowait() == {"n": 4}


async def test_no_subscribers_does_not_raise():
    b = Broadcaster()
    b.publish({"type": "status", "state": "idle"})  # must not raise
