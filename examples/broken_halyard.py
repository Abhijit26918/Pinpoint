"""What an LLM that has never seen halyard 2.3.0 plausibly writes. Try:

    pinpoint check examples/broken_halyard.py --path experiments/private_sdk
    pinpoint repair examples/broken_halyard.py --path experiments/private_sdk      # needs OPENAI_API_KEY
"""
import halyard


def drain(client: halyard.Client, queue):
    n = 0
    while True:
        job = client.dequeue(queue)  # no such method: the real one is lease()
        if job is None:
            return n
        client.complete(job)  # no such method: the real one is ack()
        n += 1


def enqueue_urgent(client: halyard.Client, queue, payload):
    return client.enqueue(queue, payload, priority=9, ttl=60)  # `ttl` is not an argument
