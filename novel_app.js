(function(){
  var BLOG_URL = 'https://zhaozhaowu.blogspot.com';
  var FEED_BASE = BLOG_URL + '/feeds/posts/default';
  var content = document.getElementById('content');
  var breadcrumb = document.getElementById('breadcrumb');

  function getPageType() {
    var path = window.location.pathname;
    var params = new URLSearchParams(window.location.search);
    var labelMatch = path.match(/\/search\/label\/(.+)/);
    if (labelMatch) return { type: 'label', label: decodeURIComponent(labelMatch[1]) };
    if (path.indexOf('/search') === 0 && params.get('q')) return { type: 'search', query: params.get('q') };
    if (path.match(/\/\d{4}\/\d{2}\//) && path.indexOf('.html') > -1) return { type: 'post', slug: path };
    return { type: 'home' };
  }

  function fetchJSON(url) { return fetch(url).then(function(r) { return r.json(); }); }

  function parsePost(entry) {
    var title = entry.title ? entry.title.$t : '';
    var link = '';
    for (var i = 0; i < (entry.link || []).length; i++) {
      if (entry.link[i].rel === 'alternate') { link = entry.link[i].href; break; }
    }
    var c = entry.content ? entry.content.$t || '' : '';
    var sn = c.replace(/<[^>]+>/g, '').substring(0, 200);
    var pub = entry.published ? entry.published.$t : '';
    var lb = [];
    if (entry.category) { for (var i = 0; i < entry.category.length; i++) lb.push(entry.category[i].term); }
    var cm = title.match(/الفصل\s+(\d+)/);
    var cn = cm ? parseInt(cm[1]) : 0;
    var tm = title.match(/من\s+(\d+)/);
    var tc = tm ? parseInt(tm[1]) : 0;
    var nn = title.replace(/\s*-\s*الفصل\s+\d+.*$/, '').trim();
    return { title:title, link:link, content:c, snippet:sn, published:pub, labels:lb, chapterNum:cn, totalChapters:tc, novelName:nn };
  }

  function groupByNovel(posts) {
    var novels = {};
    posts.forEach(function(p) {
      if (!novels[p.novelName]) novels[p.novelName] = { name:p.novelName, chapters:[], label:p.labels[0]||'' };
      novels[p.novelName].chapters.push(p);
    });
    Object.values(novels).forEach(function(n) {
      n.chapters.sort(function(a,b){return a.chapterNum-b.chapterNum;});
      n.latest = n.chapters[n.chapters.length-1];
      n.total = n.chapters.length;
    });
    return Object.values(novels).sort(function(a,b){return new Date(b.latest.published)-new Date(a.latest.published);});
  }

  function esc(s) { var d = document.createElement('div'); d.appendChild(document.createTextNode(s||'')); return d.innerHTML; }

  function renderHome() {
    breadcrumb.innerHTML = '<a href="' + BLOG_URL + '">الرئيسية</a>';
    document.title = 'روايات';
    fetchJSON(FEED_BASE + '?alt=json&max-results=200').then(function(data) {
      var entries = data.feed.entry || [];
      var posts = entries.map(parsePost);
      var novels = groupByNovel(posts);
      var h = '';
      h += '<div class="novels-section"><h2>آخر التحديثات</h2><div class="grid">';
      novels.forEach(function(n) {
        var ch = n.latest;
        h += '<div class="novel-card"><div class="card-cover"></div><div class="card-body">';
        h += '<a href="' + ch.link + '"><div class="card-title">' + esc(ch.title) + '</div></a>';
        h += '<div class="card-desc">' + esc(ch.snippet) + '</div>';
        h += '<div class="card-meta">' + n.total + ' فصل' + (n.label ? ' · ' + n.label : '') + '</div>';
        h += '</div></div>';
      });
      h += '</div></div>';
      novels.forEach(function(n) {
        h += '<div class="novels-section"><h2>' + esc(n.name) + ' <span style="font-size:14px;font-weight:400;color:#888;">(' + n.total + ' فصل)</span></h2>';
        h += '<div class="grid" style="grid-template-columns:1fr;">';
        n.chapters.forEach(function(ch) {
          h += '<div class="post" style="margin-bottom:0;"><div class="post-info">';
          h += '<div class="post-title"><a href="' + ch.link + '">' + esc(ch.title) + '</a></div>';
          h += '<div class="post-snippet">' + esc(ch.snippet) + '</div></div></div>';
        });
        h += '</div></div>';
      });
      content.innerHTML = h;
    }).catch(function() {
      content.innerHTML = '<div class="loading">خطأ في تحميل المحتوى</div>';
    });
  }

  function renderPost(slug) {
    fetchJSON(FEED_BASE + '?alt=json&max-results=200').then(function(data) {
      var entries = data.feed.entry || [];
      var posts = entries.map(parsePost);
      var cur = null;
      for (var i = 0; i < posts.length; i++) {
        if (posts[i].link.indexOf(slug) > -1) { cur = posts[i]; break; }
      }
      if (!cur) { content.innerHTML = '<div class="read-page">المقال غير موجود</div>'; return; }
      document.title = cur.title + ' - روايات';
      var sn = posts.filter(function(p){return p.novelName===cur.novelName;});
      sn.sort(function(a,b){return a.chapterNum-b.chapterNum;});
      var prev=null, next=null;
      for (var i=0;i<sn.length;i++){
        if(sn[i].chapterNum===cur.chapterNum){
          if(i>0)prev=sn[i-1];if(i<sn.length-1)next=sn[i+1];break;
        }
      }
      breadcrumb.innerHTML = '<a href="' + BLOG_URL + '">الرئيسية</a> &rsaquo; <a href="/search/label/' + encodeURIComponent(cur.labels[0]||'') + '">' + esc(cur.novelName) + '</a> &rsaquo; الفصل ' + cur.chapterNum;
      var h = '<div class="read-page"><div class="read-header"><h1>' + esc(cur.title) + '</h1>';
      h += '<div class="read-meta">الفصل ' + cur.chapterNum;
      if(cur.totalChapters)h+=' من '+cur.totalChapters;
      h+='</div></div><div class="post-body">'+cur.content+'</div>';
      h+='<div class="ad-slot">إعلان</div><div class="read-nav">';
      if(prev)h+='<a href="'+prev.link+'">← الفصل السابق</a>';else h+='<span class="disabled">الفصل السابق</span>';
      h+='<a href="'+BLOG_URL+'">الرئيسية</a>';
      if(next)h+='<a href="'+next.link+'">الفصل التالي →</a>';else h+='<span class="disabled">الفصل التالي</span>';
      h+='</div><div style="text-align:center;margin-top:24px;"><a href="/search/label/'+encodeURIComponent(cur.labels[0]||'')+'" style="color:#8B1A1A;font-weight:600;">عرض جميع فصول '+esc(cur.novelName)+'</a></div></div>';
      content.innerHTML = h;
    }).catch(function(){content.innerHTML='<div class="read-page">خطأ في تحميل المحتوى</div>';});
  }

  var page = getPageType();
  switch(page.type){
    case 'home':renderHome();break;
    case 'post':renderPost(page.slug);break;
    default:renderHome();
  }
})();
