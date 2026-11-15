import datetime
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import pytest
from django.contrib.auth.models import Permission
from django.contrib.sites.models import Site
from django.urls import reverse
from django.utils import timezone

from layerindex.models import LayerItem

DAY1 = datetime.datetime(2026, 1, 1, 12, 0)
DAY2 = datetime.datetime(2026, 1, 2, 12, 0)
DAY3 = datetime.datetime(2026, 1, 3, 12, 0)

pytestmark = pytest.mark.django_db


# --- fixtures ----------------------------------------------------------------

@pytest.fixture
def clock(monkeypatch):
    """Control the current time: ``clock.now = DAY2``."""
    class Clock:
        now = DAY1
    c = Clock()
    monkeypatch.setattr(timezone, 'now', lambda: c.now)
    return c


@pytest.fixture
def new_layer():
    """Submit a layer, which starts out unpublished ('New')."""
    def make(name, summary='A test layer', comparison=False, status='N'):
        return LayerItem.objects.create(
            name=name,
            status=status,
            layer_type='S',
            summary=summary,
            description=summary,
            vcs_url=f'git://example.com/{name}.git',
            comparison=comparison,
        )
    return make


@pytest.fixture
def publish(client, django_user_model):
    """Publish a layer through the publish view, as a reviewer."""
    reviewer = django_user_model.objects.create_user('reviewer', 'reviewer@example.com', 'pw')
    reviewer.user_permissions.add(Permission.objects.get(codename='publish_layer'))
    client.force_login(reviewer)

    def do(layer):
        response = client.get(reverse('publish', args=(layer.name,)))
        assert response.status_code == 302
        layer.refresh_from_db()
    return do


@pytest.fixture
def edit():
    """Change a layer's details and save it, e.g. ``edit(layer, summary='x')``."""
    def do(layer, **changes):
        for field, value in changes.items():
            setattr(layer, field, value)
        layer.save()
    return do


@pytest.fixture
def unpublish():
    """Take a layer out of the published state, as an admin would by
    changing the status in the admin site."""
    def do(layer, status='N'):
        layer.status = status
        layer.save()
    return do


@pytest.fixture
def site_name():
    """Name the site, as tools/site_name.py does: ``site_name('My Index')``."""
    def do(name):
        site = Site.objects.get_current()
        site.name = name
        site.save()
    yield do
    # The current site is cached outside the test's transaction
    Site.objects.clear_cache()


@pytest.fixture
def feed(client):
    """Fetch the feed. ``feed()`` lists layer names in feed order;
    ``feed.entry(name)`` gives one item's fields; ``feed.channel()`` gives
    the feed's own title and description."""
    class Feed:
        def _channel(self):
            response = client.get(reverse('published_layers_feed'))
            assert response.status_code == 200
            assert response['Content-Type'].startswith('application/rss+xml')
            return ET.fromstring(response.content).find('./channel')

        def _items(self):
            return self._channel().findall('./item')

        def channel(self):
            channel = self._channel()
            return {
                'title': channel.findtext('title'),
                'description': channel.findtext('description'),
            }

        def __call__(self):
            return [item.findtext('title') for item in self._items()]

        def entry(self, name):
            for item in self._items():
                if item.findtext('title') == name:
                    return {
                        'link': urlsplit(item.findtext('link')).path,
                        'description': item.findtext('description'),
                        'published': parsedate_to_datetime(item.findtext('pubDate')).replace(tzinfo=None),
                    }
            raise AssertionError(f'{name} is not in the feed')
    return Feed()


# --- what shows up -------------------------------------------------------------

def test_feed_is_empty_when_nothing_is_published(feed):
    assert feed() == []


def test_published_layer_is_in_the_feed(new_layer, publish, feed, clock):
    layer = new_layer('meta-foo', summary='Foo support')

    publish(layer)

    assert feed() == ['meta-foo']
    assert feed.entry('meta-foo') == {
        'link': '/layerindex/branch/master/layer/meta-foo/',
        'description': 'Foo support',
        'published': DAY1,
    }


def test_newest_published_layer_comes_first(new_layer, publish, feed, clock):
    clock.now = DAY1
    publish(new_layer('meta-older'))
    clock.now = DAY2
    publish(new_layer('meta-newer'))

    assert feed() == ['meta-newer', 'meta-older']


# --- every way of publishing counts ---------------------------------------------

def test_layer_published_in_the_admin_is_in_the_feed(new_layer, edit, feed, clock):
    # The admin form and the import tools set the status and save, without
    # going through the publish view
    layer = new_layer('meta-admin')

    clock.now = DAY2
    edit(layer, status='P')

    assert feed() == ['meta-admin']
    assert feed.entry('meta-admin')['published'] == DAY2


def test_layer_created_already_published_is_in_the_feed(new_layer, feed, clock):
    new_layer('meta-imported', status='P')

    assert feed() == ['meta-imported']
    assert feed.entry('meta-imported')['published'] == DAY1


def test_layer_published_in_the_admin_keeps_its_date_when_edited(new_layer, edit, feed, clock):
    layer = new_layer('meta-admin')
    edit(layer, status='P')

    clock.now = DAY2
    edit(layer, summary='Edited summary')

    assert feed.entry('meta-admin')['published'] == DAY1


# --- what doesn't show up -------------------------------------------------------

def test_new_layer_is_not_in_the_feed(new_layer, feed):
    new_layer('meta-waiting-for-review')

    assert feed() == []


def test_editing_an_unpublished_layer_does_not_add_it(new_layer, edit, feed):
    layer = new_layer('meta-draft')

    edit(layer, summary='Better summary')

    assert feed() == []


def test_unpublished_layer_leaves_the_feed(new_layer, publish, unpublish, feed):
    layer = new_layer('meta-withdrawn')
    publish(layer)

    unpublish(layer)

    assert feed() == []


def test_no_update_layer_is_not_in_the_feed(new_layer, publish, unpublish, feed):
    layer = new_layer('meta-frozen')
    publish(layer)

    unpublish(layer, status='X')

    assert feed() == []


def test_comparison_layer_is_not_in_the_feed(new_layer, feed):
    new_layer('meta-compare', comparison=True, status='P')

    assert feed() == []


# --- updates don't count as publishing -----------------------------------------

def test_editing_a_published_layer_keeps_its_place_and_date(new_layer, publish, edit, feed, clock):
    clock.now = DAY1
    edited = new_layer('meta-edited')
    publish(edited)
    clock.now = DAY2
    publish(new_layer('meta-untouched'))

    clock.now = DAY3
    edit(edited, summary='Edited summary')

    assert feed() == ['meta-untouched', 'meta-edited']
    assert feed.entry('meta-edited')['published'] == DAY1


def test_publishing_again_does_not_bump_the_date(new_layer, publish, feed, clock):
    clock.now = DAY1
    layer = new_layer('meta-foo')
    publish(layer)

    clock.now = DAY2
    publish(layer)

    assert feed.entry('meta-foo')['published'] == DAY1


def test_republished_layer_gets_the_new_date(new_layer, publish, unpublish, feed, clock):
    clock.now = DAY1
    layer = new_layer('meta-back')
    publish(layer)
    unpublish(layer)

    clock.now = DAY2
    publish(layer)

    assert feed.entry('meta-back')['published'] == DAY2


# --- the feed itself -------------------------------------------------------------

def test_feed_is_named_after_the_site(site_name, feed):
    site_name('My Layer Index')

    assert feed.channel() == {
        'title': 'My Layer Index - recently published layers',
        'description': 'Recently published layers',
    }


def test_feed_uses_the_default_site_name(feed):
    assert feed.channel() == {
        'title': 'OpenEmbedded Layer Index - recently published layers',
        'description': 'Recently published layers',
    }


def test_published_date_is_not_in_the_rest_api(new_layer, publish, client):
    publish(new_layer('meta-foo'))

    response = client.get('/layerindex/api/layerItems/', {'format': 'json'})

    data = response.json()
    items = data['results'] if isinstance(data, dict) else data
    (item,) = [i for i in items if i['name'] == 'meta-foo']
    assert 'published' not in item
    assert 'updated' in item


# --- discovery -----------------------------------------------------------------

def test_pages_advertise_the_feed(client):
    response = client.get(reverse('about'))

    assert 'type="application/rss+xml"' in response.content.decode()
    assert reverse('published_layers_feed') in response.content.decode()


def test_pages_link_to_the_feed_in_the_footer(client):
    # The about page has no footer
    response = client.get(reverse('history_list'))

    link = '<a href="%s">new layers feed</a>' % reverse('published_layers_feed')
    assert link in response.content.decode()
