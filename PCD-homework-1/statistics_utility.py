def collect_statistics(samples):
    """Processes collected samples to generate statistics."""
    msg_counts = [s[0] for s in samples]
    byte_counts = [s[1] for s in samples]
    time_durations = [s[2] for s in samples]
    
    return {
        'min_messages': min(msg_counts), 'avg_messages': sum(msg_counts) / len(msg_counts), 'max_messages': max(msg_counts),
        'min_bytes': min(byte_counts), 'avg_bytes': sum(byte_counts) / len(byte_counts), 'max_bytes': max(byte_counts),
        'min_time': min(time_durations), 'avg_time': sum(time_durations) / len(time_durations), 'max_time': max(time_durations),
    }

def print_statistics(protocol, size, stats):
    """Returns the collected statistics as a formatted string."""
    obj = (f"\nStatistics for {protocol} ({size}):\n"
            f"{'-' * 50}\n"
            f"Messages: Min = {stats['min_messages']}, Avg = {stats['avg_messages']:.2f}, Max = {stats['max_messages']}\n"
            f"Bytes: Min = {stats['min_bytes']}, Avg = {stats['avg_bytes']:.2f}, Max = {stats['max_bytes']}\n"
            f"Time (s): Min = {stats['min_time']:.2f}, Avg = {stats['avg_time']:.2f}, Max = {stats['max_time']:.2f}\n"
            f"{'-' * 50}\n")
    print(obj)