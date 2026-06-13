/**
 * MetaFX Tracker — Server backend
 * Node.js + Express + SQLite + JWT Auth + Meta CAPI
 *
 * Setup: npm install && node server.js
 * Config: copy .env.example to .env
 */

const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcryptjs');
const crypto = require('crypto');
const path = require('path');
const Database = require('better-sqlite3');
const fetch = require('node-fetch');
const UAParser = require('ua-parser-js');
const geoip = require('geoip-lite');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;
const JWT_SECRET = process.env.JWT_SECRET || crypto.randomBytes(32).toString('hex');
const META_ACCESS_TOKEN = process.env.META_ACCESS_TOKEN || '';
const META_PIXEL_ID = process.env.META_PIXEL_ID || '';

// ============================================================
// DATABASE SETUP
// ============================================================

const db = new Database(process.env.DB_PATH || './metafx.db');
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    name TEXT,
    role TEXT DEFAULT 'admin',
    api_key TEXT UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    domain TEXT,
    alias TEXT,
    group_id INTEGER,
    token TEXT UNIQUE NOT NULL,
    cost_model TEXT DEFAULT 'auto',
    cost_value REAL DEFAULT 0,
    meta_ad_account_id TEXT,
    meta_campaign_id TEXT,
    meta_pixel_id TEXT,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS streams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    position INTEGER DEFAULT 0,
    weight INTEGER DEFAULT 100,
    schema_type TEXT DEFAULT 'redirect',
    action_type TEXT DEFAULT 'redirect',
    action_payload TEXT,
    landing_id INTEGER,
    offer_id INTEGER,
    filters TEXT,
    status TEXT DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
  );

  CREATE TABLE IF NOT EXISTS offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    broker TEXT,
    url TEXT,
    payout_type TEXT DEFAULT 'cpa',
    payout_value REAL DEFAULT 0,
    payout_currency TEXT DEFAULT 'EUR',
    geo TEXT,
    cap_daily INTEGER,
    cap_total INTEGER,
    status TEXT DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS landings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    url TEXT,
    type TEXT DEFAULT 'prelander',
    status TEXT DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT UNIQUE NOT NULL,
    ssl_active INTEGER DEFAULT 0,
    is_primary INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS clicks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sub_id TEXT UNIQUE NOT NULL,
    campaign_id INTEGER,
    stream_id INTEGER,
    offer_id INTEGER,
    ip TEXT,
    country TEXT,
    city TEXT,
    device TEXT,
    os TEXT,
    os_version TEXT,
    browser TEXT,
    browser_version TEXT,
    language TEXT,
    referrer TEXT,
    user_agent TEXT,
    fbclid TEXT,
    utm_source TEXT,
    utm_medium TEXT,
    utm_campaign TEXT,
    utm_content TEXT,
    utm_term TEXT,
    sub_id_1 TEXT,
    sub_id_2 TEXT,
    sub_id_3 TEXT,
    sub_id_4 TEXT,
    sub_id_5 TEXT,
    cost REAL DEFAULT 0,
    is_unique INTEGER DEFAULT 1,
    is_bot INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
  );

  CREATE TABLE IF NOT EXISTS conversions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    click_id INTEGER,
    sub_id TEXT NOT NULL,
    campaign_id INTEGER,
    offer_id INTEGER,
    status TEXT NOT NULL DEFAULT 'lead',
    payout REAL DEFAULT 0,
    currency TEXT DEFAULT 'EUR',
    transaction_id TEXT,
    country TEXT,
    device TEXT,
    ip TEXT,
    meta_event_sent INTEGER DEFAULT 0,
    meta_event_id TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (click_id) REFERENCES clicks(id),
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
  );

  CREATE TABLE IF NOT EXISTS traffic_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT DEFAULT 'meta',
    api_token TEXT,
    account_id TEXT,
    status TEXT DEFAULT 'active',
    config TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    key_value TEXT UNIQUE NOT NULL,
    name TEXT,
    type TEXT DEFAULT 'live',
    status TEXT DEFAULT 'active',
    last_used DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
  );

  CREATE INDEX IF NOT EXISTS idx_clicks_campaign ON clicks(campaign_id);
  CREATE INDEX IF NOT EXISTS idx_clicks_sub_id ON clicks(sub_id);
  CREATE INDEX IF NOT EXISTS idx_clicks_created ON clicks(created_at);
  CREATE INDEX IF NOT EXISTS idx_clicks_country ON clicks(country);
  CREATE INDEX IF NOT EXISTS idx_conversions_sub_id ON conversions(sub_id);
  CREATE INDEX IF NOT EXISTS idx_conversions_campaign ON conversions(campaign_id);
  CREATE INDEX IF NOT EXISTS idx_conversions_status ON conversions(status);
  CREATE INDEX IF NOT EXISTS idx_conversions_created ON conversions(created_at);
`);

// ============================================================
// MIDDLEWARE
// ============================================================

app.use(cors());
app.use(helmet({ contentSecurityPolicy: false }));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));

const adminLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 120,
  message: { error: 'Rate limit exceeded. 120 requests per minute.' }
});

const clickLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 10000,
  message: { error: 'Rate limit exceeded.' }
});

function authenticateToken(req, res, next) {
  const apiKey = req.headers['api-key'] || req.headers['x-api-key'];
  const authHeader = req.headers['authorization'];

  if (apiKey) {
    const key = db.prepare('SELECT * FROM api_keys WHERE key_value = ? AND status = ?').get(apiKey, 'active');
    if (!key) return res.status(401).json({ error: 'Invalid API key' });
    db.prepare('UPDATE api_keys SET last_used = CURRENT_TIMESTAMP WHERE id = ?').run(key.id);
    req.userId = key.user_id;
    return next();
  }

  if (authHeader) {
    const token = authHeader.split(' ')[1];
    try {
      const decoded = jwt.verify(token, JWT_SECRET);
      req.userId = decoded.userId;
      return next();
    } catch (e) {
      return res.status(401).json({ error: 'Invalid token' });
    }
  }

  return res.status(401).json({ error: 'Authentication required' });
}

// ============================================================
// UTILITY FUNCTIONS
// ============================================================

function generateSubId() {
  return crypto.randomBytes(6).toString('base64url').toLowerCase().slice(0, 9);
}

function generateToken() {
  return crypto.randomBytes(16).toString('hex');
}

function generateApiKey(type = 'live') {
  const prefix = type === 'live' ? 'mfx_live_' : 'mfx_test_';
  return prefix + crypto.randomBytes(16).toString('hex');
}

function parseUserAgent(ua) {
  const parser = new UAParser(ua);
  const result = parser.getResult();
  return {
    device: result.device.type || 'desktop',
    os: result.os.name || 'Unknown',
    os_version: result.os.version || '',
    browser: result.browser.name || 'Unknown',
    browser_version: result.browser.version || ''
  };
}

function getGeoFromIP(ip) {
  const geo = geoip.lookup(ip);
  return {
    country: geo ? geo.country : 'XX',
    city: geo ? geo.city : 'Unknown'
  };
}

function getClientIP(req) {
  return req.headers['x-forwarded-for']?.split(',')[0]?.trim() ||
         req.headers['x-real-ip'] ||
         req.connection.remoteAddress ||
         '127.0.0.1';
}

// ============================================================
// AUTH ROUTES
// ============================================================

app.post('/api/auth/register', async (req, res) => {
  try {
    const { email, password, name } = req.body;
    if (!email || !password) return res.status(400).json({ error: 'Email and password required' });

    const hashedPassword = await bcrypt.hash(password, 12);
    const apiKey = generateApiKey('live');

    const result = db.prepare(
      'INSERT INTO users (email, password, name, api_key) VALUES (?, ?, ?, ?)'
    ).run(email, hashedPassword, name || email.split('@')[0], apiKey);

    db.prepare(
      'INSERT INTO api_keys (user_id, key_value, name, type) VALUES (?, ?, ?, ?)'
    ).run(result.lastInsertRowid, apiKey, 'Default Live Key', 'live');

    const testKey = generateApiKey('test');
    db.prepare(
      'INSERT INTO api_keys (user_id, key_value, name, type) VALUES (?, ?, ?, ?)'
    ).run(result.lastInsertRowid, testKey, 'Default Test Key', 'test');

    const token = jwt.sign({ userId: result.lastInsertRowid }, JWT_SECRET, { expiresIn: '30d' });

    res.status(201).json({
      token,
      user: { id: result.lastInsertRowid, email, name: name || email.split('@')[0] },
      api_keys: { live: apiKey, test: testKey }
    });
  } catch (e) {
    if (e.message.includes('UNIQUE')) return res.status(409).json({ error: 'Email already exists' });
    res.status(500).json({ error: 'Registration failed' });
  }
});

app.post('/api/auth/login', async (req, res) => {
  try {
    const { email, password } = req.body;
    const user = db.prepare('SELECT * FROM users WHERE email = ?').get(email);
    if (!user || !(await bcrypt.compare(password, user.password))) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    const token = jwt.sign({ userId: user.id }, JWT_SECRET, { expiresIn: '30d' });
    res.json({ token, user: { id: user.id, email: user.email, name: user.name, role: user.role } });
  } catch (e) {
    res.status(500).json({ error: 'Login failed' });
  }
});

// ============================================================
// CAMPAIGNS API
// ============================================================

app.get('/api/v1/campaigns', authenticateToken, adminLimiter, (req, res) => {
  const { status, date_from, date_to, group_id, limit = 50, offset = 0 } = req.query;

  let query = 'SELECT c.* FROM campaigns c WHERE 1=1';
  const params = [];

  if (status) { query += ' AND c.status = ?'; params.push(status); }
  if (group_id) { query += ' AND c.group_id = ?'; params.push(group_id); }
  if (date_from) { query += ' AND c.created_at >= ?'; params.push(date_from); }
  if (date_to) { query += ' AND c.created_at <= ?'; params.push(date_to + ' 23:59:59'); }

  query += ' ORDER BY c.created_at DESC LIMIT ? OFFSET ?';
  params.push(parseInt(limit), parseInt(offset));

  const campaigns = db.prepare(query).all(...params);

  const campaignsWithMetrics = campaigns.map(c => {
    const dateFilter = date_from ? `AND created_at >= '${date_from}'` : '';
    const clicks = db.prepare(`SELECT COUNT(*) as total, COUNT(CASE WHEN is_unique = 1 THEN 1 END) as unique_clicks FROM clicks WHERE campaign_id = ? ${dateFilter}`).get(c.id);
    const convs = db.prepare(`SELECT COUNT(*) as total, SUM(payout) as revenue FROM conversions WHERE campaign_id = ? ${dateFilter}`).get(c.id);
    const cost = db.prepare(`SELECT SUM(cost) as total FROM clicks WHERE campaign_id = ? ${dateFilter}`).get(c.id);

    const revenue = convs.revenue || 0;
    const totalCost = cost.total || 0;
    const profit = revenue - totalCost;

    return {
      ...c,
      metrics: {
        clicks: clicks.total,
        unique_clicks: clicks.unique_clicks,
        conversions: convs.total,
        cr: clicks.total > 0 ? ((convs.total / clicks.total) * 100).toFixed(2) : 0,
        revenue,
        cost: totalCost,
        profit,
        roi: totalCost > 0 ? ((profit / totalCost) * 100).toFixed(1) : 0,
        epc: clicks.total > 0 ? (revenue / clicks.total).toFixed(2) : 0
      }
    };
  });

  const total = db.prepare('SELECT COUNT(*) as count FROM campaigns WHERE 1=1' + (status ? ' AND status = ?' : '')).get(...(status ? [status] : []));

  res.json({ campaigns: campaignsWithMetrics, total: total.count, limit: parseInt(limit), offset: parseInt(offset) });
});

app.post('/api/v1/campaigns', authenticateToken, adminLimiter, (req, res) => {
  const { name, domain, alias, group_id, cost_model, cost_value, meta_ad_account_id, meta_campaign_id, meta_pixel_id, notes } = req.body;
  if (!name) return res.status(400).json({ error: 'Campaign name required' });

  const token = generateToken();
  const result = db.prepare(
    `INSERT INTO campaigns (name, domain, alias, group_id, token, cost_model, cost_value, meta_ad_account_id, meta_campaign_id, meta_pixel_id, notes)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
  ).run(name, domain, alias, group_id, token, cost_model || 'auto', cost_value || 0, meta_ad_account_id, meta_campaign_id, meta_pixel_id, notes);

  res.status(201).json(db.prepare('SELECT * FROM campaigns WHERE id = ?').get(result.lastInsertRowid));
});

app.put('/api/v1/campaigns/:id', authenticateToken, adminLimiter, (req, res) => {
  const { id } = req.params;
  const fields = req.body;
  const allowedFields = ['name', 'status', 'domain', 'alias', 'group_id', 'cost_model', 'cost_value', 'meta_ad_account_id', 'meta_campaign_id', 'meta_pixel_id', 'notes'];

  const updates = [];
  const values = [];
  for (const [key, value] of Object.entries(fields)) {
    if (allowedFields.includes(key)) {
      updates.push(`${key} = ?`);
      values.push(value);
    }
  }

  if (updates.length === 0) return res.status(400).json({ error: 'No valid fields to update' });
  updates.push('updated_at = CURRENT_TIMESTAMP');
  values.push(id);

  db.prepare(`UPDATE campaigns SET ${updates.join(', ')} WHERE id = ?`).run(...values);
  res.json(db.prepare('SELECT * FROM campaigns WHERE id = ?').get(id));
});

app.delete('/api/v1/campaigns/:id', authenticateToken, adminLimiter, (req, res) => {
  db.prepare('DELETE FROM campaigns WHERE id = ?').run(req.params.id);
  res.json({ success: true });
});

// ============================================================
// CLICK TRACKING API
// ============================================================

app.get('/click_api/v3', clickLimiter, (req, res) => {
  const { token, log, info, sub_id_1, sub_id_2, sub_id_3, sub_id_4, sub_id_5,
          cost, fbclid, utm_source, utm_medium, utm_campaign, utm_content, utm_term } = req.query;

  if (!token) return res.status(400).json({ error: 'Campaign token required' });

  const campaign = db.prepare('SELECT * FROM campaigns WHERE token = ? AND status = ?').get(token, 'active');
  if (!campaign) return res.status(404).json({ error: 'Campaign not found or inactive' });

  const ip = getClientIP(req);
  const ua = req.headers['user-agent'] || '';
  const parsed = parseUserAgent(ua);
  const geo = getGeoFromIP(ip);
  const subId = generateSubId();
  const referrer = req.headers['referer'] || '';

  const existingClick = db.prepare(
    "SELECT id FROM clicks WHERE campaign_id = ? AND ip = ? AND created_at > datetime('now', '-24 hours')"
  ).get(campaign.id, ip);
  const isUnique = existingClick ? 0 : 1;

  const botPatterns = /bot|crawl|spider|scrape|curl|wget|python|java|php/i;
  const isBot = botPatterns.test(ua) ? 1 : 0;

  const streams = db.prepare('SELECT * FROM streams WHERE campaign_id = ? AND status = ? ORDER BY position ASC').all(campaign.id, 'active');
  let matchedStream = streams[0];

  for (const stream of streams) {
    if (stream.filters) {
      const filters = JSON.parse(stream.filters);
      if (filters.geo && !filters.geo.includes(geo.country)) continue;
      if (filters.device && !filters.device.includes(parsed.device)) continue;
      if (filters.bot_only && !isBot) continue;
      matchedStream = stream;
      break;
    }
  }

  db.prepare(`
    INSERT INTO clicks (sub_id, campaign_id, stream_id, offer_id, ip, country, city, device, os, os_version, browser, browser_version, language, referrer, user_agent, fbclid, utm_source, utm_medium, utm_campaign, utm_content, utm_term, sub_id_1, sub_id_2, sub_id_3, sub_id_4, sub_id_5, cost, is_unique, is_bot)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run(
    subId, campaign.id, matchedStream?.id, matchedStream?.offer_id,
    ip, geo.country, geo.city, parsed.device, parsed.os, parsed.os_version,
    parsed.browser, parsed.browser_version, req.headers['accept-language'] || '',
    referrer, ua, fbclid, utm_source, utm_medium, utm_campaign, utm_content, utm_term,
    sub_id_1, sub_id_2, sub_id_3, sub_id_4, sub_id_5,
    parseFloat(cost) || 0, isUnique, isBot
  );

  let redirectUrl = matchedStream?.action_payload || campaign.domain || '';
  if (redirectUrl && !redirectUrl.startsWith('http')) redirectUrl = 'https://' + redirectUrl;

  if (redirectUrl) {
    const separator = redirectUrl.includes('?') ? '&' : '?';
    redirectUrl += `${separator}subid=${subId}`;
  }

  const response = { sub_id: subId, status: 'ok' };

  if (info === '1') {
    response.info = {
      campaign_id: campaign.id,
      stream_id: matchedStream?.id,
      sub_id: subId,
      type: matchedStream?.action_type || 'redirect',
      url: redirectUrl
    };
  }

  if (log === '1') {
    response.log = [
      `Processing campaign ${campaign.id} (${campaign.name})`,
      `IP: ${ip}`,
      `GEO: ${geo.country}/${geo.city}`,
      `Device: ${parsed.device} | ${parsed.os} | ${parsed.browser}`,
      `Unique: ${isUnique ? 'yes' : 'no'}`,
      `Bot: ${isBot ? 'yes' : 'no'}`,
      `Stream: ${matchedStream?.name || 'default'}`,
      `Redirect: ${redirectUrl}`
    ];
  }

  if (matchedStream?.action_type === 'redirect' && redirectUrl && !info) {
    return res.redirect(302, redirectUrl);
  }

  res.json(response);
});

app.post('/click_api/v3/log', clickLimiter, (req, res) => {
  const { campaign_token, url, referrer, fbclid, utm_source, utm_medium, utm_campaign } = req.body;

  const campaign = db.prepare('SELECT * FROM campaigns WHERE token = ?').get(campaign_token);
  if (!campaign) return res.status(404).json({ error: 'Campaign not found' });

  const ip = getClientIP(req);
  const ua = req.headers['user-agent'] || '';
  const parsed = parseUserAgent(ua);
  const geo = getGeoFromIP(ip);
  const subId = generateSubId();

  db.prepare(`
    INSERT INTO clicks (sub_id, campaign_id, ip, country, city, device, os, os_version, browser, browser_version, referrer, user_agent, fbclid, utm_source, utm_medium, utm_campaign, is_unique)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
  `).run(subId, campaign.id, ip, geo.country, geo.city, parsed.device, parsed.os, parsed.os_version, parsed.browser, parsed.browser_version, referrer || '', ua, fbclid, utm_source, utm_medium, utm_campaign);

  res.json({ sub_id: subId, status: 'ok' });
});

// ============================================================
// POSTBACK / CONVERSIONS
// ============================================================

app.get('/postback', async (req, res) => {
  const { subid, sub_id, status, payout, currency, tid, transaction_id } = req.query;
  const clickSubId = subid || sub_id;

  if (!clickSubId) return res.status(400).json({ error: 'subid parameter required' });
  if (!status) return res.status(400).json({ error: 'status parameter required' });

  const click = db.prepare('SELECT * FROM clicks WHERE sub_id = ?').get(clickSubId);
  if (!click) return res.status(404).json({ error: 'Click not found' });

  const convResult = db.prepare(`
    INSERT INTO conversions (click_id, sub_id, campaign_id, offer_id, status, payout, currency, transaction_id, country, device, ip)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run(
    click.id, clickSubId, click.campaign_id, click.offer_id,
    status, parseFloat(payout) || 0, currency || 'EUR',
    tid || transaction_id || null, click.country, click.device, click.ip
  );

  if (META_ACCESS_TOKEN && META_PIXEL_ID) {
    try {
      await sendMetaConversion(click, status, parseFloat(payout) || 0, convResult.lastInsertRowid);
    } catch (e) {
      console.error('Meta CAPI error:', e.message);
    }
  }

  res.json({ success: true, conversion_id: convResult.lastInsertRowid });
});

app.post('/api/v1/conversions', authenticateToken, adminLimiter, async (req, res) => {
  const { sub_id, status, payout, currency, transaction_id } = req.body;

  if (!sub_id || !status) return res.status(400).json({ error: 'sub_id and status required' });

  const click = db.prepare('SELECT * FROM clicks WHERE sub_id = ?').get(sub_id);
  if (!click) return res.status(404).json({ error: 'Click not found for given sub_id' });

  const result = db.prepare(`
    INSERT INTO conversions (click_id, sub_id, campaign_id, offer_id, status, payout, currency, transaction_id, country, device, ip)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run(click.id, sub_id, click.campaign_id, click.offer_id, status, parseFloat(payout) || 0, currency || 'EUR', transaction_id, click.country, click.device, click.ip);

  if (META_ACCESS_TOKEN && META_PIXEL_ID) {
    try {
      await sendMetaConversion(click, status, parseFloat(payout) || 0, result.lastInsertRowid);
      db.prepare('UPDATE conversions SET meta_event_sent = 1 WHERE id = ?').run(result.lastInsertRowid);
    } catch (e) {
      console.error('Meta CAPI error:', e.message);
    }
  }

  res.status(201).json({ id: result.lastInsertRowid, status: 'ok' });
});

app.get('/api/v1/conversions', authenticateToken, adminLimiter, (req, res) => {
  const { campaign_id, status, date_from, date_to, limit = 50, offset = 0 } = req.query;

  let query = 'SELECT conv.*, c.name as campaign_name FROM conversions conv LEFT JOIN campaigns c ON conv.campaign_id = c.id WHERE 1=1';
  const params = [];

  if (campaign_id) { query += ' AND conv.campaign_id = ?'; params.push(campaign_id); }
  if (status) { query += ' AND conv.status = ?'; params.push(status); }
  if (date_from) { query += ' AND conv.created_at >= ?'; params.push(date_from); }
  if (date_to) { query += ' AND conv.created_at <= ?'; params.push(date_to + ' 23:59:59'); }

  query += ' ORDER BY conv.created_at DESC LIMIT ? OFFSET ?';
  params.push(parseInt(limit), parseInt(offset));

  const conversions = db.prepare(query).all(...params);
  res.json({ conversions, total: conversions.length, limit: parseInt(limit), offset: parseInt(offset) });
});

app.put('/api/v1/conversions/:id', authenticateToken, adminLimiter, (req, res) => {
  const { status, payout } = req.body;
  const updates = [];
  const values = [];

  if (status) { updates.push('status = ?'); values.push(status); }
  if (payout !== undefined) { updates.push('payout = ?'); values.push(payout); }

  if (updates.length === 0) return res.status(400).json({ error: 'No fields to update' });
  values.push(req.params.id);

  db.prepare(`UPDATE conversions SET ${updates.join(', ')} WHERE id = ?`).run(...values);
  res.json({ success: true });
});

// ============================================================
// META CAPI INTEGRATION
// ============================================================

async function sendMetaConversion(click, eventStatus, value, conversionId) {
  const eventMap = {
    'lead': 'Lead',
    'ftd': 'Purchase',
    'deposit': 'AddPaymentInfo',
    'registration': 'CompleteRegistration',
    'qualified': 'Subscribe'
  };

  const eventName = eventMap[eventStatus.toLowerCase()] || 'Lead';
  const eventId = `mfx_${conversionId}_${Date.now()}`;

  const eventData = {
    event_name: eventName,
    event_time: Math.floor(Date.now() / 1000),
    event_id: eventId,
    event_source_url: click.referrer || undefined,
    action_source: 'website',
    user_data: {
      client_ip_address: click.ip,
      client_user_agent: click.user_agent,
      fbc: click.fbclid ? `fb.1.${Date.now()}.${click.fbclid}` : undefined,
      country: click.country ? [crypto.createHash('sha256').update(click.country.toLowerCase()).digest('hex')] : undefined
    },
    custom_data: {
      currency: 'EUR',
      value,
      content_name: `MetaFX Conversion ${eventStatus}`,
      order_id: `mfx_${conversionId}`
    }
  };

  Object.keys(eventData.user_data).forEach(k => eventData.user_data[k] === undefined && delete eventData.user_data[k]);

  const response = await fetch(
    `https://graph.facebook.com/v19.0/${META_PIXEL_ID}/events?access_token=${META_ACCESS_TOKEN}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data: [eventData] })
    }
  );

  const result = await response.json();
  if (!response.ok) throw new Error(`Meta CAPI error: ${JSON.stringify(result)}`);

  db.prepare('UPDATE conversions SET meta_event_sent = 1, meta_event_id = ? WHERE id = ?').run(eventId, conversionId);
  return result;
}

app.post('/api/v1/meta/conversions', authenticateToken, adminLimiter, async (req, res) => {
  const { conversion_ids } = req.body;

  if (!META_ACCESS_TOKEN || !META_PIXEL_ID) {
    return res.status(400).json({ error: 'Meta CAPI not configured. Set META_ACCESS_TOKEN and META_PIXEL_ID in .env' });
  }

  const results = [];
  for (const convId of (conversion_ids || [])) {
    const conv = db.prepare('SELECT conv.*, cl.* FROM conversions conv LEFT JOIN clicks cl ON conv.click_id = cl.id WHERE conv.id = ?').get(convId);
    if (conv) {
      try {
        await sendMetaConversion(conv, conv.status, conv.payout, conv.id);
        results.push({ id: convId, status: 'sent' });
      } catch (e) {
        results.push({ id: convId, status: 'error', message: e.message });
      }
    }
  }

  res.json({ results });
});

app.get('/api/v1/meta/adaccounts', authenticateToken, adminLimiter, async (req, res) => {
  if (!META_ACCESS_TOKEN) {
    return res.status(400).json({ error: 'Meta access token not configured' });
  }

  try {
    const response = await fetch(
      `https://graph.facebook.com/v19.0/me/adaccounts?fields=id,name,account_status,currency,spend_cap&access_token=${META_ACCESS_TOKEN}`
    );
    res.json(await response.json());
  } catch (e) {
    res.status(500).json({ error: 'Failed to fetch Meta ad accounts' });
  }
});

app.post('/api/v1/meta/sync', authenticateToken, adminLimiter, async (req, res) => {
  const { ad_account_id, date_from, date_to } = req.body;

  if (!META_ACCESS_TOKEN || !ad_account_id) {
    return res.status(400).json({ error: 'Meta access token and ad_account_id required' });
  }

  try {
    const timeRange = date_from && date_to ? `&time_range={"since":"${date_from}","until":"${date_to}"}` : '';
    const response = await fetch(
      `https://graph.facebook.com/v19.0/${ad_account_id}/insights?fields=campaign_name,spend,impressions,clicks,actions,cost_per_action_type&level=campaign${timeRange}&access_token=${META_ACCESS_TOKEN}`
    );
    res.json(await response.json());
  } catch (e) {
    res.status(500).json({ error: 'Failed to sync Meta data' });
  }
});

// ============================================================
// REPORTS API
// ============================================================

app.post('/api/v1/reports/build', authenticateToken, adminLimiter, (req, res) => {
  const { group_by = 'campaign', date_from, date_to, campaign_id } = req.body;

  const groupColumns = {
    campaign: 'c.name',
    country: 'cl.country',
    device: 'cl.device',
    os: 'cl.os',
    browser: 'cl.browser',
    offer: 'o.name',
    day: "strftime('%Y-%m-%d', cl.created_at)",
    hour: "strftime('%H', cl.created_at)",
    sub_id_1: 'cl.sub_id_1',
    sub_id_2: 'cl.sub_id_2',
    sub_id_3: 'cl.sub_id_3'
  };

  const groupCol = groupColumns[group_by] || 'c.name';

  let query = `
    SELECT
      ${groupCol} as group_name,
      COUNT(cl.id) as clicks,
      COUNT(CASE WHEN cl.is_unique = 1 THEN 1 END) as unique_clicks,
      COALESCE(SUM(cl.cost), 0) as cost
    FROM clicks cl
    LEFT JOIN campaigns c ON cl.campaign_id = c.id
    LEFT JOIN offers o ON cl.offer_id = o.id
    WHERE 1=1
  `;
  const params = [];

  if (date_from) { query += ' AND cl.created_at >= ?'; params.push(date_from); }
  if (date_to) { query += ' AND cl.created_at <= ?'; params.push(date_to + ' 23:59:59'); }
  if (campaign_id) { query += ' AND cl.campaign_id = ?'; params.push(campaign_id); }

  query += ` GROUP BY ${groupCol} ORDER BY clicks DESC`;

  const clickData = db.prepare(query).all(...params);

  const report = clickData.map(row => {
    let convQuery = `
      SELECT COUNT(*) as conversions, COALESCE(SUM(payout), 0) as revenue
      FROM conversions conv
      LEFT JOIN clicks cl ON conv.click_id = cl.id
      LEFT JOIN campaigns c ON cl.campaign_id = c.id
      LEFT JOIN offers o ON cl.offer_id = o.id
      WHERE 1=1
    `;
    const convParams = [];

    if (group_by === 'campaign') { convQuery += ' AND c.name = ?'; convParams.push(row.group_name); }
    else if (group_by === 'country') { convQuery += ' AND cl.country = ?'; convParams.push(row.group_name); }
    else if (group_by === 'device') { convQuery += ' AND cl.device = ?'; convParams.push(row.group_name); }
    if (date_from) { convQuery += ' AND conv.created_at >= ?'; convParams.push(date_from); }
    if (date_to) { convQuery += ' AND conv.created_at <= ?'; convParams.push(date_to + ' 23:59:59'); }

    const convData = db.prepare(convQuery).get(...convParams);
    const revenue = convData.revenue || 0;
    const profit = revenue - row.cost;

    return {
      group: row.group_name,
      clicks: row.clicks,
      unique_clicks: row.unique_clicks,
      conversions: convData.conversions,
      cr: row.clicks > 0 ? ((convData.conversions / row.clicks) * 100).toFixed(2) : '0.00',
      epc: row.clicks > 0 ? (revenue / row.clicks).toFixed(2) : '0.00',
      revenue: revenue.toFixed(2),
      cost: row.cost.toFixed(2),
      profit: profit.toFixed(2),
      roi: row.cost > 0 ? ((profit / row.cost) * 100).toFixed(1) : '0.0'
    };
  });

  res.json({ report, group_by, date_from, date_to, total_rows: report.length });
});

app.get('/api/v1/reports/export', authenticateToken, adminLimiter, (req, res) => {
  const { format = 'csv' } = req.query;

  const data = db.prepare(`
    SELECT cl.sub_id, cl.created_at, c.name as campaign, cl.country, cl.device, cl.os, cl.browser, cl.cost,
           conv.status as conv_status, conv.payout
    FROM clicks cl
    LEFT JOIN campaigns c ON cl.campaign_id = c.id
    LEFT JOIN conversions conv ON cl.id = conv.click_id
    ORDER BY cl.created_at DESC LIMIT 10000
  `).all();

  if (format === 'csv') {
    const headers = 'sub_id,date,campaign,country,device,os,browser,cost,conversion_status,payout\n';
    const rows = data.map(r => `${r.sub_id},${r.created_at},${r.campaign},${r.country},${r.device},${r.os},${r.browser},${r.cost},${r.conv_status || ''},${r.payout || 0}`).join('\n');
    res.setHeader('Content-Type', 'text/csv');
    res.setHeader('Content-Disposition', 'attachment; filename=report.csv');
    res.send(headers + rows);
  } else {
    res.json(data);
  }
});

// ============================================================
// OFFERS API
// ============================================================

app.get('/api/v1/offers', authenticateToken, adminLimiter, (req, res) => {
  res.json({ offers: db.prepare('SELECT * FROM offers ORDER BY created_at DESC').all() });
});

app.post('/api/v1/offers', authenticateToken, adminLimiter, (req, res) => {
  const { name, broker, url, payout_type, payout_value, payout_currency, geo, cap_daily, cap_total } = req.body;
  if (!name) return res.status(400).json({ error: 'Offer name required' });

  const result = db.prepare(
    'INSERT INTO offers (name, broker, url, payout_type, payout_value, payout_currency, geo, cap_daily, cap_total) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)'
  ).run(name, broker, url, payout_type || 'cpa', payout_value || 0, payout_currency || 'EUR', geo, cap_daily, cap_total);

  res.status(201).json(db.prepare('SELECT * FROM offers WHERE id = ?').get(result.lastInsertRowid));
});

app.put('/api/v1/offers/:id', authenticateToken, adminLimiter, (req, res) => {
  const allowed = ['name', 'broker', 'url', 'payout_type', 'payout_value', 'payout_currency', 'geo', 'cap_daily', 'cap_total', 'status'];
  const updates = [], values = [];

  for (const [k, v] of Object.entries(req.body)) {
    if (allowed.includes(k)) { updates.push(`${k} = ?`); values.push(v); }
  }
  if (!updates.length) return res.status(400).json({ error: 'No valid fields' });
  values.push(req.params.id);

  db.prepare(`UPDATE offers SET ${updates.join(', ')} WHERE id = ?`).run(...values);
  res.json(db.prepare('SELECT * FROM offers WHERE id = ?').get(req.params.id));
});

// ============================================================
// STREAMS API
// ============================================================

app.get('/api/v1/streams', authenticateToken, adminLimiter, (req, res) => {
  const { campaign_id } = req.query;
  let query = 'SELECT * FROM streams';
  const params = [];
  if (campaign_id) { query += ' WHERE campaign_id = ?'; params.push(campaign_id); }
  query += ' ORDER BY position ASC';
  res.json({ streams: db.prepare(query).all(...params) });
});

app.post('/api/v1/streams', authenticateToken, adminLimiter, (req, res) => {
  const { campaign_id, name, weight, schema_type, action_type, action_payload, landing_id, offer_id, filters } = req.body;
  if (!campaign_id || !name) return res.status(400).json({ error: 'campaign_id and name required' });

  const position = db.prepare('SELECT MAX(position) as max_pos FROM streams WHERE campaign_id = ?').get(campaign_id);
  const result = db.prepare(
    'INSERT INTO streams (campaign_id, name, position, weight, schema_type, action_type, action_payload, landing_id, offer_id, filters) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
  ).run(campaign_id, name, (position.max_pos || 0) + 1, weight || 100, schema_type || 'redirect', action_type || 'redirect', action_payload, landing_id, offer_id, filters ? JSON.stringify(filters) : null);

  res.status(201).json(db.prepare('SELECT * FROM streams WHERE id = ?').get(result.lastInsertRowid));
});

app.put('/api/v1/streams/:id', authenticateToken, adminLimiter, (req, res) => {
  const allowed = ['name', 'weight', 'schema_type', 'action_type', 'action_payload', 'landing_id', 'offer_id', 'filters', 'status', 'position'];
  const updates = [], values = [];

  for (const [k, v] of Object.entries(req.body)) {
    if (allowed.includes(k)) { updates.push(`${k} = ?`); values.push(k === 'filters' ? JSON.stringify(v) : v); }
  }
  if (!updates.length) return res.status(400).json({ error: 'No valid fields' });
  values.push(req.params.id);

  db.prepare(`UPDATE streams SET ${updates.join(', ')} WHERE id = ?`).run(...values);
  res.json(db.prepare('SELECT * FROM streams WHERE id = ?').get(req.params.id));
});

// ============================================================
// DOMAINS API
// ============================================================

app.get('/api/v1/domains', authenticateToken, adminLimiter, (req, res) => {
  res.json({ domains: db.prepare('SELECT * FROM domains ORDER BY is_primary DESC, created_at DESC').all() });
});

app.post('/api/v1/domains', authenticateToken, adminLimiter, (req, res) => {
  const { domain, ssl_active, is_primary } = req.body;
  if (!domain) return res.status(400).json({ error: 'Domain required' });

  if (is_primary) db.prepare('UPDATE domains SET is_primary = 0').run();
  const result = db.prepare('INSERT INTO domains (domain, ssl_active, is_primary) VALUES (?, ?, ?)').run(domain, ssl_active ? 1 : 0, is_primary ? 1 : 0);
  res.status(201).json(db.prepare('SELECT * FROM domains WHERE id = ?').get(result.lastInsertRowid));
});

// ============================================================
// CLICKS LOG API
// ============================================================

app.get('/api/v1/clicks', authenticateToken, adminLimiter, (req, res) => {
  const { campaign_id, country, device, date_from, date_to, limit = 100, offset = 0 } = req.query;

  let query = 'SELECT cl.*, c.name as campaign_name FROM clicks cl LEFT JOIN campaigns c ON cl.campaign_id = c.id WHERE 1=1';
  const params = [];

  if (campaign_id) { query += ' AND cl.campaign_id = ?'; params.push(campaign_id); }
  if (country) { query += ' AND cl.country = ?'; params.push(country); }
  if (device) { query += ' AND cl.device = ?'; params.push(device); }
  if (date_from) { query += ' AND cl.created_at >= ?'; params.push(date_from); }
  if (date_to) { query += ' AND cl.created_at <= ?'; params.push(date_to + ' 23:59:59'); }

  query += ' ORDER BY cl.created_at DESC LIMIT ? OFFSET ?';
  params.push(parseInt(limit), parseInt(offset));

  res.json({ clicks: db.prepare(query).all(...params) });
});

// ============================================================
// DASHBOARD STATS API
// ============================================================

app.get('/api/v1/dashboard/stats', authenticateToken, adminLimiter, (req, res) => {
  const { period = '7d' } = req.query;
  const periodMap = { '1d': '-1 day', '7d': '-7 days', '30d': '-30 days', 'mtd': '-30 days' };
  const dateFilter = periodMap[period] || '-7 days';

  const clicks = db.prepare(`SELECT COUNT(*) as total, COUNT(CASE WHEN is_unique = 1 THEN 1 END) as unique_total FROM clicks WHERE created_at >= datetime('now', ?)`).get(dateFilter);
  const convs = db.prepare(`SELECT COUNT(*) as total, SUM(payout) as revenue FROM conversions WHERE created_at >= datetime('now', ?)`).get(dateFilter);
  const cost = db.prepare(`SELECT SUM(cost) as total FROM clicks WHERE created_at >= datetime('now', ?)`).get(dateFilter);

  const revenue = convs.revenue || 0;
  const totalCost = cost.total || 0;
  const profit = revenue - totalCost;

  res.json({
    clicks: clicks.total,
    unique_clicks: clicks.unique_total,
    conversions: convs.total,
    cr: clicks.total > 0 ? ((convs.total / clicks.total) * 100).toFixed(2) : '0.00',
    revenue: revenue.toFixed(2),
    cost: totalCost.toFixed(2),
    profit: profit.toFixed(2),
    roi: totalCost > 0 ? ((profit / totalCost) * 100).toFixed(1) : '0.0',
    epc: clicks.total > 0 ? (revenue / clicks.total).toFixed(2) : '0.00',
    cpl: convs.total > 0 ? (totalCost / convs.total).toFixed(2) : '0.00'
  });
});

app.get('/api/v1/dashboard/chart', authenticateToken, adminLimiter, (req, res) => {
  const { period = '7d' } = req.query;
  const days = period === '30d' ? 30 : period === '1d' ? 1 : 7;

  const data = [];
  for (let i = days - 1; i >= 0; i--) {
    const dayData = db.prepare(`
      SELECT date(cl.created_at) as date, COUNT(cl.id) as clicks, COALESCE(SUM(cl.cost), 0) as cost
      FROM clicks cl WHERE date(cl.created_at) = date('now', '-${i} days')
    `).get();

    const convData = db.prepare(`
      SELECT COUNT(*) as conversions, COALESCE(SUM(payout), 0) as revenue
      FROM conversions WHERE date(created_at) = date('now', '-${i} days')
    `).get();

    data.push({
      date: dayData.date || new Date(Date.now() - i * 86400000).toISOString().split('T')[0],
      clicks: dayData.clicks,
      cost: dayData.cost,
      conversions: convData.conversions,
      revenue: convData.revenue
    });
  }

  res.json({ chart_data: data });
});

// ============================================================
// API KEYS MANAGEMENT
// ============================================================

app.get('/api/v1/api-keys', authenticateToken, adminLimiter, (req, res) => {
  const keys = db.prepare('SELECT id, name, type, status, key_value, last_used, created_at FROM api_keys WHERE user_id = ?').all(req.userId);
  const masked = keys.map(k => ({
    ...k,
    key_value: k.key_value.slice(0, 12) + '...' + k.key_value.slice(-4)
  }));
  res.json({ api_keys: masked });
});

app.post('/api/v1/api-keys', authenticateToken, adminLimiter, (req, res) => {
  const { name, type = 'live' } = req.body;
  const keyValue = generateApiKey(type);
  db.prepare('INSERT INTO api_keys (user_id, key_value, name, type) VALUES (?, ?, ?, ?)').run(req.userId, keyValue, name || `Key ${Date.now()}`, type);
  res.status(201).json({ key: keyValue, name, type });
});

// ============================================================
// TRACKING SCRIPT
// ============================================================

app.get('/mfx.min.js', (req, res) => {
  res.setHeader('Content-Type', 'application/javascript');
  res.send(`
(function(){
  var MFX = window.MFX = {};
  MFX.init = function(config) {
    var params = new URLSearchParams(window.location.search);
    var data = {
      campaign_token: config.campaign_token,
      url: window.location.href,
      referrer: document.referrer,
      fbclid: params.get('fbclid'),
      utm_source: params.get('utm_source'),
      utm_medium: params.get('utm_medium'),
      utm_campaign: params.get('utm_campaign'),
      utm_content: params.get('utm_content'),
      utm_term: params.get('utm_term')
    };

    if (config.track_params) {
      config.track_params.forEach(function(p) { data[p] = params.get(p); });
    }

    var domain = config.domain || window.location.hostname;
    fetch('https://' + domain + '/click_api/v3/log', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    }).then(function(r) { return r.json(); })
    .then(function(result) {
      MFX.sub_id = result.sub_id;
      if (config.auto_subid) {
        document.querySelectorAll('a[href*="{subid}"]').forEach(function(a) {
          a.href = a.href.replace('{subid}', result.sub_id);
        });
        document.querySelectorAll('form').forEach(function(f) {
          var input = document.createElement('input');
          input.type = 'hidden';
          input.name = 'subid';
          input.value = result.sub_id;
          f.appendChild(input);
        });
      }
    }).catch(function(e) { console.warn('MFX tracking error:', e); });
  };

  MFX.conversion = function(status, payout, config) {
    if (!MFX.sub_id) return;
    var domain = (config && config.domain) || window.location.hostname;
    fetch('https://' + domain + '/postback?subid=' + MFX.sub_id + '&status=' + status + '&payout=' + (payout || 0));
  };
})();
  `);
});

// ============================================================
// HEALTH + FRONTEND
// ============================================================

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', version: '1.0.0', timestamp: new Date().toISOString() });
});

app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// ============================================================
// START SERVER
// ============================================================

app.listen(PORT, () => {
  console.log(`\n🚀 MetaFX Tracker running on http://localhost:${PORT}`);
  console.log(`📊 Dashboard: http://localhost:${PORT}`);
  console.log(`📌 API Base: http://localhost:${PORT}/api/v1`);
  console.log(`📡 Click API: http://localhost:${PORT}/click_api/v3`);
  console.log(`📥 Postback: http://localhost:${PORT}/postback\n`);
});

module.exports = app;
