"""Discovery only: uses the SDK CLI, never creates/enables an Arm."""


def main():
    from motomind_milly.identity import main as discover
    return discover()
