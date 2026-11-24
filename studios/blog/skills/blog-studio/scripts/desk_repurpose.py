"""Repurpose on the desk: a repurpose job's output becomes a new desk blog, once.

Part of desk_finish, which keeps every name its callers use.
"""

import desk
import desk_images
import studio


def repurpose(root, ident, job_id, title, content):
    """Make a repurpose job's output a new desk blog, once: the job's receipt names it."""
    import tool_jobs

    job = tool_jobs.read(root, job_id)
    if job.get('kind') != 'repurpose' or (job.get('metadata') or {}).get('article') != ident:
        raise ValueError('Choose prepared copy from this blog.')
    if (job.get('metadata') or {}).get('format') == 'meta':
        raise ValueError('A meta description is kept with its post, not made a new blog.')
    if job.get('applied'):
        made = job['applied'].get('desk') if isinstance(job['applied'], dict) else None
        if made:
            return made
        raise ValueError('This copy was already saved. Prepare it again for a new blog.')
    if job.get('status') != 'ready':
        raise ValueError('Wait for the prepared copy before making it a blog.')
    if not isinstance(content, str) or not content.strip() or len(content) > desk.LIMIT:
        raise ValueError('Keep the prepared copy, up to 200,000 characters.')
    if not isinstance(title, str) or not title.strip() or '\n' in title.strip() or len(title) > 500:
        raise ValueError('Give the new blog a title of one line, up to 500 characters.')
    source = desk.read(root, ident)
    data = {'title': title.strip(), 'manuscript': content, 'tone': source.get('tone') or ''}
    if source.get('style'):
        try:
            studio.style_check(root, source['style']['style_id'])
            data['style'] = source['style']['style_id']
        except (ValueError, KeyError, TypeError):
            pass  # A retired kind of post: the copy is a blog of no particular kind.
    # The images the copy names come with it, so the new blog does not open without them.
    images = source.get('images') or {}
    if images and desk_images.REFERENCE.search(content):
        held = desk._data(root, ident)
        named = desk_images.written(
            {'title': '', 'opening': content, 'sections': [], 'images': images}
        )
        lines = desk_images.definitions(
            {
                'title': '',
                'opening': content,
                'sections': [],
                'images': {n: images[n] for n in named},
            },
            held,
        )
        if lines:
            data['manuscript'] = content.rstrip() + '\n\n' + '\n\n'.join(lines) + '\n'
    made = desk.create(root, data)
    job['applied'] = {'desk': {'id': made['id'], 'title': made['title']}, 'posted': False}
    job['saved_content'] = content
    tool_jobs.write(root, job)
    return job['applied']['desk']
