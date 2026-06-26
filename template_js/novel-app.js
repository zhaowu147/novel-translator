/**
 * Novel reading website - JavaScript for Blogger
 * Reads Blogger Feed API and renders novel grid / chapter list / search
 * NO template literals (backticks) - Blogger XML corrupts them
 */

(function() {
  'use strict';

  var BLOG_URL = window.location.origin;
  var FEED_URL = BLOG_URL + '/feeds/posts/default?alt=json';
  var LABELS_URL = BLOG_URL + '/feeds/posts/default/-/';

  var allPosts = [];
  var novelMap = {};

  function esc(s) {
    var d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
  }

  function fetchPosts(label, maxResults) {
    var url = label
      ? LABELS_URL + encodeURIComponent(label) + '?alt=json&max-results=' + (maxResults || 500)
      : FEED_URL + '&max-results=' + (maxResults || 500);

    return fetch(url)
      .then(function(resp) { return resp.json(); })
      .then(function(data) { return data.feed.entry || []; })
      .catch(function(e) { console.error('Feed error:', e); return []; });
  }

  function parseEntry(entry) {
    var title = entry.title ? entry.title.$t : '';
    var content = entry.content ? entry.content.$t : '';
    var published = entry.published ? entry.published.$t : '';

    var url = '';
    if (entry.link) {
      for (var i = 0; i < entry.link.length; i++) {
        if (entry.link[i].rel === 'alternate') { url = entry.link[i].href; break; }
      }
    }

    var labels = [];
    if (entry.category) {
      entry.category.forEach(function(c) { if (c.term) labels.push(c.term); });
    }

    var thumbnail = '';
    if (entry.media$thumbnail) {
      thumbnail = entry.media$thumbnail.url;
    } else if (entry.media$group && entry.media$group.media$thumbnail) {
      thumbnail = entry.media$group.media$thumbnail[0].url;
    }

    var tmp = document.createElement('div');
    tmp.innerHTML = content;
    var text = tmp.textContent || tmp.innerText || '';
    var snippet = text.substring(0, 200).trim() + (text.length > 200 ? '...' : '');

    var chapterNum = 0;
    var chMatch = title.match(/الفصل\s+(\d+)/);
    if (chMatch) chapterNum = parseInt(chMatch[1]);

    return { title: title, url: url, published: published, labels: labels, thumbnail: thumbnail, snippet: snippet, chapterNum: chapterNum };
  }

  function buildNovelMap(posts) {
    var map = {};
    posts.forEach(function(post) {
      var novelLabels = post.labels.filter(function(l) {
        return l !== 'روايات' && l !== 'مكتملة' && l !== 'مستمرة' &&
          !/^(رومانسي|خيال|تاريخي|أكشن|خيال علمي)$/.test(l);
      });
      var label = novelLabels.length > 0 ? novelLabels[0] : null;
      if (!label) return;

      if (!map[label]) {
        map[label] = { title: label, posts: [], cover: post.thumbnail || '', snippet: post.snippet, latestDate: post.published };
      }
      map[label].posts.push(post);
      if (post.published > map[label].latestDate) {
        map[label].latestDate = post.published;
        if (post.thumbnail && !map[label].cover) map[label].cover = post.thumbnail;
      }
    });

    Object.keys(map).forEach(function(key) {
      map[key].posts.sort(function(a, b) { return a.chapterNum - b.chapterNum; });
      if (map[key].posts.length > 0) map[key].snippet = map[key].posts[0].snippet;
    });
    return map;
  }

  function renderNovelGrid(container, novels) {
    container.innerHTML = '';
    var grid = document.createElement('div');
    grid.className = 'grid';

    Object.keys(novels).forEach(function(key) {
      var novel = novels[key];
      var card = document.createElement('a');
      card.className = 'novel-card';
      card.href = novel.posts[0] ? novel.posts[0].url : '#';

      var coverHtml = novel.cover
        ? '<img src="' + novel.cover + '" alt="' + novel.title + '">'
        : '<div style="width:100%;height:100%;background:linear-gradient(135deg,#ddd,#bbb);"></div>';

      card.innerHTML =
        '<div class="card-cover">' + coverHtml + '</div>' +
        '<div class="card-body">' +
          '<div class="card-title">' + esc(novel.title) + '</div>' +
          '<div class="card-desc">' + esc(novel.snippet) + '</div>' +
          '<div class="card-meta">' + novel.posts.length + ' فصل</div>' +
        '</div>';
      grid.appendChild(card);
    });

    container.appendChild(grid);
  }

  function renderChapterList(container, novel) {
    container.innerHTML = '';

    var coverHtml = novel.cover
      ? '<img src="' + novel.cover + '" alt="' + novel.title + '">'
      : '<div style="width:100%;height:100%;background:linear-gradient(135deg,#ddd,#bbb);"></div>';

    var hero = document.createElement('div');
    hero.className = 'novel-hero';
    hero.innerHTML =
      '<div class="novel-cover">' + coverHtml + '</div>' +
      '<div class="novel-detail">' +
        '<h1>' + esc(novel.title) + '</h1>' +
        '<div class="synopsis">' + esc(novel.snippet) + '</div>' +
        '<a class="start-btn" href="' + (novel.posts[0] ? novel.posts[0].url : '#') + '">ابدأ القراءة</a>' +
      '</div>';
    container.appendChild(hero);

    var chapters = document.createElement('div');
    chapters.className = 'chapters';
    chapters.innerHTML =
      '<div class="ch-header">' +
        '<h2>قائمة الفصول</h2>' +
        '<span>' + novel.posts.length + ' فصل</span>' +
      '</div>';

    novel.posts.forEach(function(post) {
      var item = document.createElement('div');
      item.className = 'ch-item';
      var date = post.published.split('T')[0];
      item.innerHTML =
        '<div class="ch-info">' +
          '<div class="ch-title"><a href="' + post.url + '">' + esc(post.title) + '</a></div>' +
          '<div class="ch-meta">' + date + '</div>' +
        '</div>' +
        '<a class="ch-read" href="' + post.url + '">اقرأ</a>';
      chapters.appendChild(item);
    });

    container.appendChild(chapters);
  }

  function initSearch() {
    var searchInput = document.querySelector('.nav-search');
    if (!searchInput) return;
    searchInput.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        var query = this.value.trim();
        if (query) window.location.href = BLOG_URL + '/search?q=' + encodeURIComponent(query);
      }
    });
  }

  function init() {
    var isHome = document.body.classList.contains('index');
    var isLabel = window.location.pathname.indexOf('/search/label/') !== -1;

    if (!isHome && !isLabel) return;

    var mainSection = document.querySelector('#main, .main, [id*="main"]');
    if (!mainSection) return;

    var gridContainer = mainSection.querySelector('.novels-grid');
    if (!gridContainer && !isLabel) return;

    console.log('Fetching posts...');
    fetchPosts(null, 500).then(function(entries) {
      console.log('Fetched ' + entries.length + ' posts');
      allPosts = entries.map(parseEntry);
      novelMap = buildNovelMap(allPosts);
      console.log('Found ' + Object.keys(novelMap).length + ' novels');

      if (isHome && gridContainer) {
        var heading = gridContainer.querySelector('h2');
        if (heading) heading.textContent = 'أحدث الروايات';
        renderNovelGrid(gridContainer, novelMap);
      }

      if (isLabel) {
        var labelMatch = window.location.pathname.match(/\/search\/label\/(.+)/);
        if (labelMatch) {
          var label = decodeURIComponent(labelMatch[1]);
          if (novelMap[label]) {
            mainSection.innerHTML = '';
            renderChapterList(mainSection, novelMap[label]);
          }
        }
      }

    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  initSearch();

})();
