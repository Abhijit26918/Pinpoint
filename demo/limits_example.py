import halyard


def count_processed(client: halyard.Client, queue):
    done = 0
    for job in client.peek(queue, limit=100):
        client.ack(job)          # acks jobs it never leased or processed
        done = 1                 # should be done += 1
    return done
