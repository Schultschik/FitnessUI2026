(() => {
  if (window.__fitnessKiosk) return window.__fitnessKiosk.tick();
  const nav = { index: 0, playbackIndex: 0, homeRequested: false, lastUrl: '', userPaused: false };
  const style = document.createElement('style');
  style.textContent = `
    #fitness-controls { position:fixed; top:24px; right:24px; z-index:2147483647;
      display:flex; gap:12px; padding:8px; background:#111c; border-radius:8px; }
    #fitness-controls button { font:700 24px sans-serif; color:white; background:#222;
      border:3px solid #666; border-radius:6px; padding:16px 24px; cursor:pointer; }
    #fitness-controls button[data-selected="true"] { border-color:#42e8b6; background:#17393d; }
    [data-fitness-selected="true"] { outline:5px solid #42e8b6!important; outline-offset:3px; }
  `;
  document.head.appendChild(style);
  const controls = document.createElement('div');
  controls.id = 'fitness-controls';
  const play = document.createElement('button');
  play.textContent = 'Play / Pause';
  const home = document.createElement('button');
  home.textContent = 'Home';
  home.title = 'Stop YouTube and return to Fitness';
  controls.append(play, home);
  const video = () => document.querySelector('video');
  const watching = () => location.pathname === '/watch';
  const visible = el => el.getClientRects().length > 0;
  const entries = () => {
    const found = [];
    const seen = new Set();
    const selector = 'ytd-video-renderer a#video-title, ytd-playlist-renderer a#video-title, ' +
      'ytd-playlist-renderer a#thumbnail, ytd-radio-renderer a#thumbnail, ' +
      'ytd-playlist-video-renderer a#video-title, yt-lockup-view-model a[href]';
    for (const link of document.querySelectorAll(selector)) {
      if (!visible(link)) continue;
      const url = new URL(link.href, location.href);
      if (!['/watch', '/playlist'].includes(url.pathname)) continue;
      const key = url.searchParams.get('v') || url.searchParams.get('list');
      if (!key || seen.has(key)) continue;
      seen.add(key); found.push(link);
    }
    return found;
  };
  const stop = () => {
    video()?.pause();
    nav.homeRequested = true;
  };
  const toggle = () => {
    const v = video();
    nav.userPaused = v ? !v.paused : true;
    if (v) v.paused ? v.play().catch(() => {}) : v.pause();
  };
  home.onclick = stop;
  play.onclick = toggle;
  function choose(link) {
    if (!link) return;
    const url = new URL(link.href, location.href);
    if (url.pathname === '/playlist') sessionStorage.setItem('fitness-playlist', '1');
    link.click();
  }
  document.addEventListener('click', event => {
    if (event.isTrusted && event.target.closest('.ytp-play-button, video')) nav.userPaused = !video()?.paused;
    const link = event.target.closest('a[href]');
    if (link && new URL(link.href, location.href).pathname === '/playlist') {
      sessionStorage.setItem('fitness-playlist', '1');
    }
  }, true);
  nav.key = key => {
    if (key === 'Escape' || key.toLowerCase() === 'h') { stop(); return; }
    if (watching()) {
      if (key === 'ArrowUp' || key === 'ArrowDown') nav.playbackIndex = 1 - nav.playbackIndex;
      if (key === 'Enter' || key === ' ') nav.playbackIndex === 1 ? stop() : toggle();
    } else {
      const links = entries();
      if (key === 'ArrowDown') nav.index = (nav.index + 1) % (links.length + 1);
      if (key === 'ArrowUp') nav.index = (nav.index + links.length) % (links.length + 1);
      if (key === 'Enter') nav.index === links.length ? stop() : choose(links[nav.index]);
      if (key.startsWith('Arrow')) links[nav.index]?.scrollIntoView({ block: 'center' });
    }
    nav.paint();
  };
  document.addEventListener('keydown', event => {
    if (event.target.matches('input,textarea,[contenteditable="true"]')) return;
    if (!['ArrowUp', 'ArrowDown', 'Enter', ' ', 'Escape', 'h', 'H'].includes(event.key)) return;
    event.preventDefault(); event.stopImmediatePropagation(); nav.key(event.key);
  }, true);
  nav.paint = () => {
    document.querySelectorAll('[data-fitness-selected]').forEach(el => el.removeAttribute('data-fitness-selected'));
    const links = entries();
    nav.index = Math.min(nav.index, links.length);
    if (!watching()) links[nav.index]?.setAttribute('data-fitness-selected', 'true');
    play.hidden = !watching();
    play.dataset.selected = String(watching() && nav.playbackIndex === 0);
    home.dataset.selected = String(watching() ? nav.playbackIndex === 1 : nav.index === links.length);
    play.textContent = video()?.paused ? 'Play' : 'Pause';
  };
  nav.tick = () => {
    if (nav.lastUrl !== location.href) {
      nav.lastUrl = location.href; nav.userPaused = false; nav.playbackIndex = 0; nav.index = 0;
    }
    const v = video();
    const player = document.querySelector('#movie_player');
    // Keep controls inside the fullscreen element so they remain visible in the top layer.
    const parent = document.fullscreenElement || document.body;
    if (controls.parentNode !== parent) parent.appendChild(controls);
    if (!nav.homeRequested && watching() && v && player) {
      if (!nav.userPaused && v.readyState >= 2) {
        // YouTube may pause again while initializing or switching away from an ad.
        if (v.paused) {
          if (typeof player.playVideo === 'function') player.playVideo();
          v.play().catch(() => {});
        }
      }
      if (!document.fullscreenElement) player.requestFullscreen().catch(() => {});
    }
    if (location.pathname === '/playlist' && sessionStorage.getItem('fitness-playlist')) {
      const first = entries().find(link => new URL(link.href).pathname === '/watch');
      if (first) { sessionStorage.removeItem('fitness-playlist'); choose(first); }
    }
    if (watching()) sessionStorage.removeItem('fitness-playlist');
    nav.paint();
    return { homeRequested: nav.homeRequested, watching: watching(), fullscreen: !!document.fullscreenElement };
  };
  window.__fitnessKiosk = nav;
  return nav.tick();
})();
