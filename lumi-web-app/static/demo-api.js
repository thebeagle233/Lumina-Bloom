/* Static exhibition mode: no geolocation, API requests, secrets or model calls. */
(() => {
  'use strict';
  window.LUMI_DEMO = true;
  const candidates = [
    { name: 'Sample Pocket Park', type: 'park', distance_m: 160, walk_min: 2 },
    { name: 'Sample Community Garden', type: 'garden', distance_m: 320, walk_min: 4 },
    { name: 'Sample Waterfront Walk', type: 'outdoor_spot', distance_m: 480, walk_min: 6 },
  ].map(place => ({ ...place, map_url: '' }));

  window.lumiDemoRequest = async (url, payload = {}) => {
    const route = new URL(url, 'https://lumi.example').pathname;
    if (route === '/api/weather') {
      return { source: 'demo-sample', temperature_c: 24, uv_index: 4, cloud_cover: 30,
        precipitation: 0, is_day: true };
    }
    if (route === '/api/places') {
      return { source: 'demo-sample', count: candidates.length,
        candidate_places: candidates.map(place => ({ ...place })) };
    }
    if (route === '/api/agent/recommend') {
      const reasons = payload.recent_behavior?.skip_reasons || [];
      const lastReason = reasons[reasons.length - 1];
      const minutes = reasons.length ? 5 : 10;
      const nudge = lastReason === 'busy'
        ? 'A busy day can still hold one small pause. Try a 5-minute outdoor break when you have space.'
        : lastReason === 'mood'
          ? 'No pressure today. Take a quiet pause, and step outside for 5 minutes only if it feels right.'
          : lastReason === 'lazy'
            ? 'Let us make the first step tiny: shoes on, then a gentle 5-minute reset.'
            : 'A little daylight, a little room to breathe. Try a gentle 10-minute outdoor break.';
      return {
        provider: 'demo-local-rules', suggested_duration_min: minutes, nudge_text: nudge,
        decision_type: 'go_out_now', tone: 'gentle', reason_tags: ['demo'],
        follow_up_options: ['Try a tiny break', 'Come back later'],
        place_recommendations: candidates.map((place, index) => ({ ...place,
          recommendation_score: 92 - index * 8,
          recommendation_label: index === 0 ? 'Excellent' : 'Good',
          why: `Illustrative spot, about ${place.walk_min} minutes away.`,
        })),
        biometric_estimate: {
          stress_label: lastReason === 'mood' ? 'HIGH' : 'MODERATE',
          stress_pct: lastReason === 'mood' ? 75 : 45,
          slacking_probability_pct: lastReason === 'mood' ? 70 : 40,
          slack_subtext: 'Illustrative pattern only; no sensors or health measurement.',
        },
      };
    }
    if (route === '/api/bloom/chat') {
      const text = `${payload.message || ''} ${payload.context?.body_state || ''}`.toLowerCase();
      let reply = "I'm here with you. One small step is enough today; you can choose the pace.";
      if (/tired|sleep|exhaust|累|困/.test(text)) {
        reply = 'You can pause and rest for a moment. A sip of water and a slower breath are enough for now.';
      } else if (/stress|anxious|sad|overwhelm|焦虑|难过/.test(text)) {
        reply = "That sounds like a lot to carry. Let us take one gentle breath together; there is no need to rush.";
      } else if (Number(payload.context?.sunlight_today_min || 0) > 0) {
        reply = 'You made a little room for yourself today. I am growing with each moment you choose to record.';
      }
      return { ok: true, provider: 'demo-scripted-replies', reply, fallback_used: false };
    }
    throw new Error(`Unsupported demo route: ${route}`);
  };
})();
