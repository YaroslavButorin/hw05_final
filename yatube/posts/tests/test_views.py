import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache

from ..models import Group, Post, Comment, Follow

User = get_user_model()
POST_PER_PAGE = settings.POST_LIMIT_PER_PAGE

TEMP_MEDIA_FOLDER = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_FOLDER)
class PostPagesTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test_group',
            description='Тестовое описание',
        )
        cls.uploaded = SimpleUploadedFile(
            name='small.gif',
            content=(
                b'\x47\x49\x46\x38\x39\x61\x02\x00'
                b'\x01\x00\x80\x00\x00\x00\x00\x00'
                b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
                b'\x00\x00\x00\x2C\x00\x00\x00\x00'
                b'\x02\x00\x01\x00\x00\x02\x02\x0C'
                b'\x0A\x00\x3B'
            ),
            content_type='image/gif'
        )
        cls.user = User.objects.create_user(username='auth')
        for x in range(15):
            cls.post = Post.objects.create(
                author=cls.user,
                group=cls.group,
                text='Тестовый пост',
                image=cls.uploaded
            )

            cls.comment_post = Comment.objects.create(
                author=cls.user,
                text='кек',
                post=cls.post
            )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_FOLDER, ignore_errors=True)

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        cache.clear()

    def test_pages_uses_correct_template(self):
        """-"""
        templates_pages_names = {
            'posts/index.html': reverse('posts:index'),
            'posts/group_list.html': reverse(
                'posts:group_list',
                kwargs={'slug': self.group.slug}),
            'posts/profile.html': reverse('posts:profile',
                                          kwargs={
                                              'username':
                                                  self.user}),
            'posts/post_detail.html': reverse(
                'posts:post_detail',
                kwargs={'post_id': self.post.pk}),
            'posts/create_post.html': [
                reverse('posts:post_edit', kwargs={
                    'post_id': self.post.pk}),
                reverse('posts:post_create'), ]}
        for template, reverse_name in templates_pages_names.items():
            print(template, reverse_name)
            with self.subTest(reverse_name=reverse_name):
                if type(reverse_name) == list:
                    for x in reverse_name:
                        response = self.authorized_client.get(x)
                        self.assertTemplateUsed(response, template)
                else:
                    response = self.authorized_client.get(reverse_name)
                    self.assertTemplateUsed(response, template)

    def test_post_index_page_show_correct_context(self):
        """-"""
        response = self.authorized_client.get(reverse('posts:index'))
        self.assertEqual(len(response.context['page_obj'].object_list),
                         POST_PER_PAGE)
        self.assertIn(
            '.gif',
            self.post.image.name

        )
        response = self.client.get(reverse('posts:index') + '?page=2')
        self.assertEqual(len(response.context['page_obj']), POST_PER_PAGE - 5)

    def test_posts_group_list_pages_show_correct_context(self):
        """-"""
        response = (self.authorized_client.get(
            reverse('posts:group_list', kwargs={'slug': self.group.slug})))
        self.assertEqual(response.context.get('group').title,
                         self.post.group.title)
        self.assertEqual(response.context['page_obj'][0].text,
                         self.post.text)
        self.assertIn('.gif', str(self.post.image))
        self.assertEqual(len(response.context['page_obj']), POST_PER_PAGE)
        response = self.client.get(reverse('posts:group_list', kwargs={
            'slug': self.group.slug}) + '?page=2')
        self.assertEqual(len(response.context['page_obj']),
                         POST_PER_PAGE - 5)

    def test_posts_profile_pages_show_correct_context(self):
        """-"""
        response = (self.authorized_client.get(
            reverse('posts:profile', kwargs={'username': self.user})))
        self.assertEqual(response.context['page_obj'].object_list[0].group,
                         self.group)
        self.assertEqual(response.context['page_obj'].object_list[0].text,
                         self.post.text)
        self.assertEqual(response.context['page_obj'].object_list[0].author,
                         self.post.author)
        self.assertIn('.gif', str(self.post.image))
        self.assertEqual(len(response.context['page_obj']), POST_PER_PAGE)
        response = self.client.get(reverse('posts:profile', kwargs={
            'username': self.user}) + '?page=2')
        self.assertEqual(len(response.context['page_obj']), POST_PER_PAGE - 5)

    def test_posts_detail_pages_show_correct_context(self):
        """-"""
        response = (self.authorized_client.get(
            reverse('posts:post_detail', kwargs={'post_id': self.post.pk})))
        self.assertEqual(response.context['post'].author, self.user)
        self.assertEqual(response.context['post'].group, self.group)
        self.assertEqual(response.context['post'].text, self.post.text)
        self.assertEqual(response.context['post'].pk, self.post.pk)
        self.assertEqual(response.context['post'].image, self.post.image)

    def test_posts_edit_pages_show_correct_context(self):
        """-"""
        response = (
            self.authorized_client.get(
                reverse('posts:post_edit', kwargs={'post_id': self.post.pk}))
        )
        is_edit = response.context['is_edit']
        self.assertTrue(is_edit)

    def test_posts_create_pages_show_correct_context(self):
        """-"""
        response = (self.authorized_client.
                    get(reverse('posts:post_create')))

        is_edit = response.context['form']
        self.assertTrue(is_edit)

    def test_index_caches(self):
        new_post = Post.objects.create(
            author=PostPagesTests.user,
            text='testt',
            group=PostPagesTests.group
        )

        response_1 = self.authorized_client.get(
            reverse('posts:index')
        )

        response_content_1 = response_1.content
        new_post.delete()

        response_2 = self.authorized_client.get(
            reverse('posts:index')
        )
        response_content_2 = response_2.content
        self.assertEqual(response_content_1, response_content_2)
        cache.clear()

        response_3 = self.authorized_client.get(
            reverse('posts:index')
        )
        response_content_3 = response_3.content
        self.assertNotEqual(response_content_2, response_content_3)

    def post_exist(self, page_context):
        if 'page_obj' in page_context:
            post = page_context['page_obj'][-1]
        else:
            post = page_context['post']
        author = post.author
        text = post.text
        image = post.image
        group = post.group
        self.assertIn(
            '.gif',
            image.name

        )
        self.assertEqual(
            author,
            PostPagesTests.post.author
        )
        self.assertEqual(
            text,
            PostPagesTests.post.text
        )
        self.assertEqual(
            group,
            PostPagesTests.post.group
        )
        self.assertEqual(
            post.comments.last().text,
            PostPagesTests.comment_post.text
        )

    def test_follow(self):
        count_follow = Follow.objects.count()
        new_author = User.objects.create(username='ElvisPresley')
        self.authorized_client.get(
            reverse(
                'posts:profile_follow',
                kwargs={'username': new_author.username}
            )
        )
        follow = Follow.objects.last()

        self.assertEqual(Follow.objects.count(), count_follow + 1)
        self.assertEqual(follow.author, new_author)
        self.assertEqual(follow.user, self.user)

    def test_unfollow(self):
        count_follow = Follow.objects.count()
        new_author = User.objects.create(username='ElvisPresley')
        self.authorized_client.get(
            reverse(
                'posts:profile_follow',
                kwargs={'username': new_author.username}
            )
        )
        self.assertEqual(Follow.objects.count(), count_follow + 1)
        self.authorized_client.get(
            reverse(
                'posts:profile_unfollow',
                kwargs={'username': new_author.username}
            )
        )
        self.assertEqual(Follow.objects.count(), count_follow)

    def test_following_posts(self):
        new_user = User.objects.create(username='ElvisPresley')
        authorized_client = Client()
        authorized_client.force_login(new_user)
        authorized_client.get(
            reverse(
                'posts:profile_follow',
                kwargs={'username': PostPagesTests.user.username}
            )
        )
        response_follow = authorized_client.get(
            reverse('posts:follow_index')
        )
        context_follow = response_follow.context
        self.post_exist(context_follow)

    def test_unfollowing_posts(self):
        new_user = User.objects.create(username='Lermontov')
        authorized_client = Client()
        authorized_client.force_login(new_user)
        response_unfollow = authorized_client.get(
            reverse('posts:follow_index')
        )
        context_unfollow = response_unfollow.context
        self.assertEqual(len(context_unfollow['page_obj']), 0)
