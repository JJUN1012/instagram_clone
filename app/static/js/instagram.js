const { screen, username, postId } = document.body.dataset;
const select = (selector, root = document) => root.querySelector(selector);
const profileUrl = (name) => '/users/' + encodeURIComponent(name);
const postUrl = (id) => '/posts/' + encodeURIComponent(id);
const status = select('#status');
const imageTypes = ['image/jpeg', 'image/png', 'image/webp'];
let viewer;

function node(tag, value = '', css = '') {
  const element = document.createElement(tag);
  element.textContent = value;
  if (css) element.className = css;
  return element;
}

function link(href, value, css) {
  const element = node('a', value, css);
  element.href = href;
  return element;
}

function showStatus(message = '', error = false) {
  status.hidden = !message;
  status.textContent = message;
  status.classList.toggle('error', error);
}

async function api(path, { method = 'GET', body } = {}) {
  const json = body !== undefined && !(body instanceof FormData);
  const response = await fetch('/api/v1' + path, {
    method,
    credentials: 'same-origin',
    headers: { Accept: 'application/json', ...(json ? { 'Content-Type': 'application/json' } : {}) },
    body: json ? JSON.stringify(body) : body,
  });
  const hasJson = ![204, 205].includes(response.status)
    && response.headers.get('content-type')?.includes('application/json');
  const data = hasJson ? await response.json() : null;
  if (!response.ok) {
    if (response.status === 401 && !['login', 'signup'].includes(screen)) {
      location.assign('/login');
      throw new Error('로그인이 필요합니다.');
    }
    const detail = typeof data?.detail === 'string' ? data.detail : null;
    throw new Error(data?.error?.message || detail || '요청을 처리하지 못했어요. 다시 시도해 주세요.');
  }
  return data;
}

async function run(button, action) {
  if (button?.disabled) return;
  if (button) button.disabled = true;
  showStatus();
  try {
    await action();
  } catch (error) {
    showStatus(error.message, true);
  } finally {
    if (button) button.disabled = false;
  }
}

function bindForm(id, action) {
  const form = select(id);
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    run(event.submitter || select('[type=submit]', form), () => action(form, new FormData(form)));
  });
}

function image(src, alt, css) {
  const element = node('img', '', css);
  element.alt = alt;
  element.loading = 'lazy';
  element.src = src;
  return element;
}

function avatar(user) {
  const wrapper = node('span', '', 'avatar');
  const initials = (user.name || user.username || '?').slice(0, 1);
  wrapper.textContent = initials;
  if (user.profile_image_url) {
    const photo = image(user.profile_image_url, '');
    photo.addEventListener('error', () => photo.remove());
    wrapper.append(photo);
  }
  return wrapper;
}

function identity(user) {
  const result = link(user.username === viewer?.username ? '/me' : profileUrl(user.username), '', 'identity');
  result.append(avatar(user), node('strong', user.username));
  return result;
}

function displayDate(value) {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? '' : new Intl.DateTimeFormat(
    'ko-KR', { month: 'long', day: 'numeric', hour: 'numeric', minute: '2-digit' },
  ).format(date);
}

function setEmpty(container, message) {
  container.append(node(container.tagName === 'UL' ? 'li' : 'p', message, 'empty'));
}

function imagesOf(post) {
  return Array.isArray(post.image_urls) && post.image_urls.length
    ? post.image_urls : [post.image_url].filter(Boolean);
}

function postCard(post) {
  const card = select('#post-card').content.firstElementChild.cloneNode(true);
  select('.identity', card).replaceWith(identity(post.author));
  const time = select('time', card);
  time.textContent = displayDate(post.created_at);
  time.dateTime = post.created_at || '';

  const photos = imagesOf(post);
  if (photos.length) {
    let index = 0;
    const media = select('.post-media', card);
    const photo = select('img', media);
    const previous = select('.previous', media);
    const next = select('.next', media);
    const position = select('.photo-index', media);
    media.hidden = false;
    photo.loading = 'lazy';
    select('.photo-open', media).addEventListener('click', () => {
      if (screen !== 'post') {
        location.assign(postUrl(post.id));
        return;
      }
      const url = new URL(photos[index], location.origin);
      if (['https:', 'http:'].includes(url.protocol)) {
        window.open(url.href, '_blank', 'noopener,noreferrer');
      }
    });
    function showPhoto() {
      photo.src = photos[index];
      photo.alt = '게시물 사진 ' + (index + 1);
      position.textContent = (index + 1) + ' / ' + photos.length;
      position.hidden = photos.length < 2;
      previous.hidden = index === 0;
      next.hidden = index === photos.length - 1;
    }
    previous.onclick = () => { index -= 1; showPhoto(); };
    next.onclick = () => { index += 1; showPhoto(); };
    showPhoto();
  }

  const likeButton = select('.like-button', card);
  const likeCount = select('.like-count', card);
  let liked = Boolean(post.liked_by_me);
  let count = post.like_count ?? 0;
  function showLikes() {
    likeButton.setAttribute('aria-pressed', String(liked));
    likeButton.setAttribute('aria-label', liked ? '좋아요 취소' : '좋아요');
    likeCount.textContent = '좋아요 ' + count + '개';
  }
  likeButton.onclick = () => run(likeButton, async () => {
    const data = await api(postUrl(post.id) + '/likes', { method: liked ? 'DELETE' : 'POST' });
    if (Number.isInteger(data?.like_count) && typeof data.liked_by_me === 'boolean') {
      ({ liked_by_me: liked, like_count: count } = data);
    } else {
      const updated = await api(postUrl(post.id));
      ({ liked_by_me: liked, like_count: count } = updated);
    }
    showLikes();
  });
  showLikes();

  const caption = select('.caption', card);
  if (post.content) caption.append(link(profileUrl(post.author.username), post.author.username), ' ' + post.content);
  else caption.hidden = true;
  card.querySelectorAll('.comment-link').forEach((item) => {
    item.href = postUrl(post.id) + '/comments';
  });
  select('.comment-count', card).dataset.count = post.comment_count ?? 0;
  select('.comment-count', card).textContent = post.comment_count > 0
    ? '댓글 ' + post.comment_count + '개 보기' : '댓글 달기';

  const follow = select('.follow-button', card);
  if (screen === 'feed' && viewer.username !== post.author.username) {
    const path = profileUrl(post.author.username);
    let followed = post.author.followed_by_me ?? true;
    function showFollowing() {
      follow.textContent = followed ? '팔로잉' : '팔로우';
      follow.setAttribute('aria-pressed', String(followed));
    }
    follow.hidden = false;
    showFollowing();
    follow.onclick = () => run(follow, async () => {
      const result = await api(path + '/follow', { method: followed ? 'DELETE' : 'POST' });
      const updated = typeof result?.followed_by_me === 'boolean' ? result : await api(path);
      followed = updated.followed_by_me;
      document.dispatchEvent(new CustomEvent('followingchange', {
        detail: { username: post.author.username, followed },
      }));
    });
    document.addEventListener('followingchange', (event) => {
      if (event.detail.username === post.author.username) {
        followed = event.detail.followed;
        showFollowing();
      }
    });
  }

  const remove = select('.delete-post', card);
  if (viewer && viewer.username === post.author.username) {
    remove.hidden = false;
    remove.onclick = () => {
      if (!window.confirm('이 게시물을 삭제할까요?')) return;
      run(remove, async () => {
        await api(postUrl(post.id), { method: 'DELETE' });
        if (screen === 'post') location.assign('/timeline');
        else card.remove();
      });
    };
  }
  return card;
}

function updateDetailCommentCount(delta) {
  const label = select('#post .comment-count');
  if (!label) return;
  const count = Math.max(0, Number(label.dataset.count) + delta);
  label.dataset.count = count;
  label.textContent = count ? '댓글 ' + count + '개 보기' : '댓글 달기';
}

function commentRow(comment) {
  const item = node('li', '', 'list-row');
  item.dataset.commentId = comment.id;
  const body = node('div', '', 'comment-body');
  const who = identity(comment.author);
  const content = node('p', comment.content);
  const time = node('time', displayDate(comment.created_at));
  time.dateTime = comment.created_at || '';
  const meta = node('div', '', 'comment-meta');
  meta.append(who, time);
  body.append(meta, content);
  item.append(body);
  if (viewer?.username === comment.author.username) {
    const remove = node('button', '삭제', 'text-button');
    remove.type = 'button';
    remove.onclick = () => {
      if (!window.confirm('이 댓글을 삭제할까요?')) return;
      run(remove, async () => {
        await api('/comments/' + encodeURIComponent(comment.id), { method: 'DELETE' });
        item.remove();
        updateDetailCommentCount(-1);
        if (!select('#comment-list').children.length) setEmpty(select('#comment-list'), '아직 댓글이 없어요.');
      });
    };
    item.append(remove);
  }
  return item;
}

async function appendPages(path, container, render, emptyText, busyContainer = container) {
  const button = select('#load-more');
  let cursor = null;
  async function load() {
    const query = new URLSearchParams({ limit: 20 });
    if (cursor) query.set('cursor', cursor);
    try {
      const page = await api(path + '?' + query);
      if (page.items.length) select('.empty', container)?.remove();
      page.items.forEach((item) => container.append(render(item)));
      if (!container.children.length) setEmpty(container, emptyText);
      cursor = page.next_cursor;
      button.hidden = !cursor;
    } finally {
      busyContainer.setAttribute('aria-busy', 'false');
    }
  }
  button.onclick = () => run(button, load);
  await load();
}

async function showComments() {
  const container = select('#comment-list');
  const form = select('#comment-form');
  const submit = select('button', form);
  submit.disabled = true;
  const path = postUrl(postId) + '/comments';
  select('#comment-avatar').replaceChildren(avatar(viewer));
  if (screen === 'comments') setBack('/timeline', (path) => path === '/timeline' || path === postUrl(postId));
  else setBack('/timeline', (path) => path === '/me' || /^\/users\/[^/]+$/.test(path));
  bindForm('#comment-form', async (form, values) => {
    const content = values.get('content').trim();
    if (!content) throw new Error('댓글 내용을 입력해 주세요.');
    const comment = await api(path, { method: 'POST', body: { content } });
    select('.empty', container)?.remove();
    if (!Array.from(container.children).some((row) => row.dataset.commentId === String(comment.id))) {
      container.prepend(commentRow(comment));
    }
    updateDetailCommentCount(1);
    form.reset();
    select('input', form).focus();
  });
  const load = node('button', '댓글 더 보기', 'secondary');
  load.type = 'button';
  load.hidden = true;
  container.after(load);
  let cursor = null;
  async function loadComments() {
    const query = new URLSearchParams({ limit: 20 });
    if (cursor) query.set('cursor', cursor);
    const page = await api(path + '?' + query);
    for (const comment of page.items) container.append(commentRow(comment));
    if (!container.children.length) setEmpty(container, '아직 댓글이 없어요.');
    cursor = page.next_cursor;
    load.hidden = !cursor;
  }
  load.onclick = () => run(load, loadComments);
  try {
    const tasks = [loadComments()];
    if (screen === 'post') tasks.push(api(postUrl(postId)).then((post) => select('#post').append(postCard(post))));
    await Promise.all(tasks);
    submit.disabled = false;
  } finally {
    container.setAttribute('aria-busy', 'false');
  }
}

async function showProfile() {
  const target = username || viewer.username;
  const path = profileUrl(target);
  const container = select('#profile');
  try {
    const profile = await api(path);
    const { user, counts } = profile;
    const header = node('section', '', 'panel profile');
    const profileAvatar = avatar(user);
    profileAvatar.classList.add('profile-avatar');
    const info = node('div', '', 'profile-info');
    select('#page-title').textContent = user.username;
    info.append(node('h2', user.name || user.username));
    const numbers = node('div', '', 'stats');
    function stat(label, count, href) {
      const container = href ? link(href, '') : node('span');
      container.append(node('strong', count), node('span', label));
      return container;
    }
    numbers.append(
      stat('게시물', counts.post_count),
      stat('팔로워', counts.follower_count, path + '/followers'),
      stat('팔로잉', counts.following_count, path + '/following'),
    );
    const actions = node('div', '', 'profile-actions');
    if (user.username === viewer.username) {
      actions.append(link('/users/me/edit', '프로필 편집', 'secondary'));
    } else {
      const button = node('button', '', 'primary');
      button.type = 'button';
      let following = Boolean(profile.followed_by_me);
      const refresh = () => { button.textContent = following ? '팔로잉' : '팔로우'; };
      refresh();
      button.onclick = () => run(button, async () => {
        const data = await api(path + '/follow', { method: following ? 'DELETE' : 'POST' });
        const current = data?.counts ? data : await api(path);
        following = Boolean(current.followed_by_me);
        select('strong', numbers.children[1]).textContent = current.counts.follower_count;
        refresh();
      });
      actions.append(button);
    }
    info.append(numbers);
    header.append(profileAvatar, info);
    if (user.bio) header.append(node('p', user.bio, 'bio'));
    header.append(actions);
    const gridHeader = select('#profile-grid-heading').content.cloneNode(true);
    const grid = node('section', '', 'grid');
    grid.setAttribute('aria-label', '게시물');
    const more = node('button', '게시물 더 보기', 'secondary');
    more.id = 'load-more';
    more.type = 'button';
    more.hidden = true;
    container.append(header, gridHeader, grid, more);
    await appendPages(path + '/posts', grid, (post) => {
      const tile = link(postUrl(post.id), '', 'tile');
      tile.setAttribute('aria-label', '게시물 ' + post.id);
      const cover = imagesOf(post)[0];
      if (cover) tile.append(image(cover, ''));
      else tile.textContent = post.content || '게시물';
      return tile;
    }, '아직 게시물이 없어요.', container);
  } finally {
    container.setAttribute('aria-busy', 'false');
  }
}

function setupAuth() {
  bindForm('#auth-form', async (_, values) => {
    const body = { username: values.get('username').trim(), password: values.get('password') };
    if (!body.username) throw new Error('아이디를 입력해 주세요.');
    if (screen === 'signup') {
      body.name = values.get('name').trim();
      if (!body.name) throw new Error('이름을 입력해 주세요.');
      if (body.password !== values.get('password_confirm')) throw new Error('비밀번호 확인이 일치하지 않아요.');
    }
    await api('/auth/' + screen, { method: 'POST', body });
    location.assign(screen === 'signup' ? '/login' : '/timeline');
  });
}

function setupEdit() {
  const form = select('#edit-form');
  for (const field of ['name', 'username', 'bio']) form.elements[field].value = viewer[field] || '';
  select('#edit-actions').disabled = false;
  const photo = select('#profile-preview');
  let tempUrl;
  function updatePhoto(src) {
    photo.hidden = !src;
    if (src) photo.src = src;
    else photo.removeAttribute('src');
  }
  updatePhoto(viewer.profile_image_url);
  form.elements.profile_image.onchange = () => {
    showStatus();
    if (tempUrl) URL.revokeObjectURL(tempUrl);
    const file = form.elements.profile_image.files[0];
    if (file && !imageTypes.includes(file.type)) {
      form.elements.profile_image.value = '';
      showStatus('JPEG, PNG, WebP 사진을 선택해 주세요.', true);
    }
    tempUrl = form.elements.profile_image.files[0]
      ? URL.createObjectURL(form.elements.profile_image.files[0]) : null;
    updatePhoto(tempUrl || viewer.profile_image_url);
  };
  bindForm('#edit-form', async (_, body) => {
    for (const field of ['name', 'username']) {
      const value = body.get(field).trim();
      if (!value) throw new Error('이름과 아이디를 입력해 주세요.');
      body.set(field, value);
    }
    if (!body.get('profile_image').size) body.delete('profile_image');
    await api('/users/me', { method: 'PATCH', body });
    location.assign('/me');
  });
}

function setupUpload() {
  const form = select('#upload-form');
  const picker = form.elements.images;
  const list = select('#previews');
  const chosen = [];
  function redraw() {
    list.replaceChildren();
    chosen.forEach(({ file, url }, index) => {
      const item = node('li', '', 'preview');
      item.append(image(url, file.name));
      const controls = node('div', '', 'preview-actions');
      for (const [text, label, direction] of [['←', '앞으로 이동', -1], ['→', '뒤로 이동', 1], ['×', '사진 제거', 0]]) {
        const button = node('button', text, 'icon-button');
        button.type = 'button';
        button.setAttribute('aria-label', (index + 1) + '번 사진 ' + label);
        const target = index + direction;
        button.disabled = target < 0 || target >= chosen.length;
        button.onclick = () => {
          if (direction) [chosen[index], chosen[target]] = [chosen[target], chosen[index]];
          else URL.revokeObjectURL(chosen.splice(index, 1)[0].url);
          redraw();
          list.children[Math.min(target, chosen.length - 1)]?.querySelector('button:not(:disabled)')?.focus();
        };
        controls.append(button);
      }
      item.append(controls);
      list.append(item);
    });
  }
  picker.onchange = () => {
    showStatus();
    const files = Array.from(picker.files);
    picker.value = '';
    if (chosen.length + files.length > 10) return showStatus('사진은 최대 10장까지 선택할 수 있어요.', true);
    if (files.some((file) => !imageTypes.includes(file.type) || !file.size)) {
      return showStatus('올바른 JPEG, PNG, WebP 사진을 선택해 주세요.', true);
    }
    files.forEach((file) => chosen.push({ file, url: URL.createObjectURL(file) }));
    redraw();
  };
  form.elements.content.oninput = () => {
    select('#caption-count').textContent = form.elements.content.value.length + ' / 2000';
  };
  bindForm('#upload-form', async (_, body) => {
    if (!chosen.length) throw new Error('사진을 한 장 이상 선택해 주세요.');
    body.delete('images');
    chosen.forEach(({ file }) => body.append('images', file));
    await api('/posts', { method: 'POST', body });
    location.assign('/timeline');
  });
}

function setBack(fallback, acceptsSource) {
  const back = select('#back-link');
  if (!back) return;
  back.href = fallback;
  if (!acceptsSource || !document.referrer) return;
  const source = new URL(document.referrer);
  if (source.origin !== location.origin || !acceptsSource(source.pathname)) return;
  back.href = source.pathname + source.search;
  back.addEventListener('click', (event) => {
    if (history.length < 2 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    history.back();
  });
}

async function start() {
  if (screen === 'login' || screen === 'signup') return setupAuth();
  viewer = await api('/users/me');
  select('#nav-profile')?.replaceChildren(avatar(viewer));
  if (screen === 'feed') return appendPages('/feed', select('#feed'), postCard, '표시할 게시물이 없어요.');
  if (screen === 'profile') {
    setBack('/timeline', (path) => path === '/timeline' || /^\/posts\/[^/]+(?:\/comments)?$/.test(path)
      || /^\/users\/[^/]+\/(followers|following)$/.test(path));
    return showProfile();
  }
  if (screen === 'post' || screen === 'comments') return showComments();
  if (screen === 'followers' || screen === 'following') {
    const path = profileUrl(username);
    setBack(username === viewer.username ? '/me' : path, (source) => source === '/me' || source === path);
    const { counts } = await api(path);
    select('[data-tab="followers"]').textContent = '팔로워 ' + counts.follower_count;
    select('[data-tab="following"]').textContent = '팔로잉 ' + counts.following_count;
    return appendPages(path + '/' + screen, select('#people'), (user) => {
      const row = node('li', '', 'list-row');
      row.append(identity(user));
      if (user.name) row.append(node('span', user.name));
      return row;
    }, '목록이 비어 있어요.');
  }
  if (screen === 'edit') {
    select('#back-link').href = '/me';
    return setupEdit();
  }
  if (screen === 'upload') {
    setBack('/timeline', (path) => path === '/timeline' || path === '/me');
    return setupUpload();
  }
  if (screen === 'settings') {
    select('#back-link').href = '/me';
    const button = select('#logout');
    button.onclick = () => run(button, async () => {
      await api('/auth/logout', { method: 'POST' });
      location.assign('/login');
    });
  }
  if (screen === 'password') {
    select('#back-link').href = '/setting';
    bindForm('#password-form', async (_, values) => {
      const { current_password, new_password, password_confirm } = Object.fromEntries(values);
      if (new_password !== password_confirm) throw new Error('새 비밀번호 확인이 일치하지 않아요.');
      await api('/users/me/password', { method: 'PATCH', body: { current_password, new_password } });
      location.assign('/setting');
    });
  }
}

run(null, start);
