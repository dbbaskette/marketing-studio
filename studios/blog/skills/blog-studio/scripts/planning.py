"""Local advisory overlap search; historical matches are leads, never current evidence."""

import blog_library


def report(root, topic):
    if not isinstance(topic, str) or not topic.strip() or len(topic) > 500:
        raise ValueError('Give a proposed topic up to 500 characters.')
    found = blog_library.catalog(root, query=topic.strip(), limit=10, reusable_only=True)
    return {
        'topic': topic.strip(),
        'items': found['items'],
        'total': found['total'],
        'advisory': True,
        'changed': False,
        'next_step': 'Read matching posts before drafting. Similar wording is a lead, not proof of duplication or current factual support. No matches means only that this exact local search found none.',
    }


def add_parser(groups):
    parser = groups.add_parser(
        'plan', help='Find local topic-overlap leads without changing writing decisions'
    )
    parser.add_argument('--topic', required=True)
