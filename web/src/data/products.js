/**
 * products.js — Static product catalogue for the RateWeaver e-commerce storefront.
 *
 * Each product includes:
 *   - Catalogue metadata (id, name, category, description, imageUrl)
 *   - Ecommerce domain signals that map directly to the backend pack:
 *       category        → enum: electronics | fashion | grocery | home_appliances | beauty
 *       mrp             → number (Maximum Retail Price in INR)
 *       inventory_pct   → number 0–100 (current stock level)
 *       demand_score    → number 0–100 (current demand)
 *       days_since_listed → integer (listing age in days)
 *   - Optional context signals (customer_tier, quantity, is_flash_sale set at store level)
 *
 * These are realistic demo values — not fabricated dynamic prices.
 * Actual prices come from POST /v1/price via the backend.
 */

// Accurate, clean product photography for everyday Indian e-commerce catalogue
const IMG = {
  // Electronics
  earphones:    '/products/earphones.png',
  keyboard:     '/products/keyboard.png',
  phonecase:    '/products/phonecase.png',
  powerbank:    'https://images.unsplash.com/photo-1609091839311-d5365f9ff1c5?w=400&q=80',

  // Fashion
  tshirt:       'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=400&q=80',
  backpack:     'https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=400&q=80',
  cap:          'https://images.unsplash.com/photo-1521369909029-2afed882baee?w=400&q=80',
  socks:        '/products/socks.png',

  // Grocery
  coffee:       '/products/coffee.png',
  oats:         'https://images.unsplash.com/photo-1517673400267-0251440c45dc?w=400&q=80',

  // Home Appliances
  lamp:         'https://images.unsplash.com/photo-1507473885765-e6ed057f782c?w=400&q=80',
  lunchbox:     '/products/lunchbox.png',

  // Beauty
  facewash:     '/products/facewash.png',
  lipbalm:      '/products/lipbalm.png',
};


// Category display labels
export const CATEGORY_LABELS = {
  electronics:     'Electronics',
  fashion:         'Fashion',
  grocery:         'Grocery',
  home_appliances: 'Home Appliances',
  beauty:          'Beauty',
};

export const CATEGORIES = Object.keys(CATEGORY_LABELS);

/**
 * Main product catalogue — 14 everyday Indian e-commerce products.
 *
 * `signals` contains ONLY the fields defined in packs/ecommerce.json.
 * No custom fields are sent to the backend.
 */
export const PRODUCTS = [
  /* ─── Electronics ─────────────────────────────────────────────── */
  {
    id: 'ec-001',
    name: 'boAt Bassheads 100 Earphones',
    shortDesc: 'In-ear wired earphones with mic, 10mm drivers, tangle-free cable.',
    category_label: 'Electronics',
    imageUrl: IMG.earphones,
    rating: 4.3,
    reviewCount: 12400,
    signals: {
      category: 'electronics',
      mrp: 699,
      inventory_pct: 72,
      demand_score: 68,
      days_since_listed: 210,
    },
  },
  {
    id: 'ec-002',
    name: 'Zebronics Zeb-K500 Mechanical Keyboard',
    shortDesc: 'USB wired mechanical keyboard, rainbow LED backlight, 104 keys.',
    category_label: 'Electronics',
    imageUrl: IMG.keyboard,
    rating: 4.1,
    reviewCount: 3870,
    signals: {
      category: 'electronics',
      mrp: 1299,
      inventory_pct: 45,
      demand_score: 55,
      days_since_listed: 95,
    },
  },
  {
    id: 'ec-003',
    name: 'Spigen Rugged Armor Phone Case',
    shortDesc: 'Military-grade drop protection case with matte carbon texture.',
    category_label: 'Electronics',
    imageUrl: IMG.phonecase,
    rating: 4.5,
    reviewCount: 8920,
    signals: {
      category: 'electronics',
      mrp: 999,
      inventory_pct: 8,           // very low → scarcity premium
      demand_score: 82,           // viral demand
      days_since_listed: 30,
    },
  },
  {
    id: 'ec-004',
    name: 'Ambrane 20000mAh Power Bank',
    shortDesc: 'Dual USB output, 18W fast charging, compact design, LED indicator.',
    category_label: 'Electronics',
    imageUrl: IMG.powerbank,
    rating: 4.0,
    reviewCount: 6120,
    signals: {
      category: 'electronics',
      mrp: 1799,
      inventory_pct: 88,          // excess inventory → markdown
      demand_score: 40,
      days_since_listed: 300,     // aging listing → clearance
    },
  },

  /* ─── Fashion ──────────────────────────────────────────────────── */
  {
    id: 'fa-001',
    name: "Bewakoof Men's Round Neck T-Shirt",
    shortDesc: 'Pure cotton, regular fit, graphic print, available in multiple colours.',
    category_label: 'Fashion',
    imageUrl: IMG.tshirt,
    rating: 4.2,
    reviewCount: 22000,
    signals: {
      category: 'fashion',
      mrp: 599,
      inventory_pct: 60,
      demand_score: 75,
      days_since_listed: 45,
    },
  },
  {
    id: 'fa-002',
    name: 'Wildcraft Daypack 25L Backpack',
    shortDesc: 'Water-resistant nylon, padded straps, laptop compartment.',
    category_label: 'Fashion',
    imageUrl: IMG.backpack,
    rating: 4.4,
    reviewCount: 9800,
    signals: {
      category: 'fashion',
      mrp: 1499,
      inventory_pct: 22,          // low inventory → mild scarcity
      demand_score: 63,
      days_since_listed: 120,
    },
  },
  {
    id: 'fa-003',
    name: 'WROGN Snapback Cap',
    shortDesc: 'Structured snapback, embroidered logo, one-size-fits-most.',
    category_label: 'Fashion',
    imageUrl: IMG.cap,
    rating: 3.9,
    reviewCount: 4200,
    signals: {
      category: 'fashion',
      mrp: 499,
      inventory_pct: 85,          // excess → clearance
      demand_score: 30,
      days_since_listed: 195,     // aging
    },
  },
  {
    id: 'fa-004',
    name: "Cotstyle Men's Ankle Socks (Pack of 5)",
    shortDesc: 'Breathable cotton blend, anti-slip heel, casual everyday wear.',
    category_label: 'Fashion',
    imageUrl: IMG.socks,
    rating: 4.6,
    reviewCount: 31000,
    signals: {
      category: 'fashion',
      mrp: 349,
      inventory_pct: 55,
      demand_score: 50,
      days_since_listed: 60,
    },
  },

  /* ─── Grocery ──────────────────────────────────────────────────── */
  {
    id: 'gr-001',
    name: 'Nescafé Classic Instant Coffee 200g',
    shortDesc: 'Rich roasted flavour, 100% pure coffee, resealable jar.',
    category_label: 'Grocery',
    imageUrl: IMG.coffee,
    rating: 4.5,
    reviewCount: 48000,
    signals: {
      category: 'grocery',
      mrp: 475,
      inventory_pct: 65,
      demand_score: 72,
      days_since_listed: 10,
    },
  },
  {
    id: 'gr-002',
    name: 'Quaker Rolled Oats 1kg',
    shortDesc: 'Whole grain oats, high fibre, quick 3-minute cook time.',
    category_label: 'Grocery',
    imageUrl: IMG.oats,
    rating: 4.3,
    reviewCount: 18500,
    signals: {
      category: 'grocery',
      mrp: 230,
      inventory_pct: 78,
      demand_score: 55,
      days_since_listed: 20,
    },
  },

  /* ─── Home Appliances ──────────────────────────────────────────── */
  {
    id: 'ha-001',
    name: 'Philips LED Desk Lamp',
    shortDesc: 'Eye-care technology, adjustable brightness, USB charging port.',
    category_label: 'Home Appliances',
    imageUrl: IMG.lamp,
    rating: 4.2,
    reviewCount: 5600,
    signals: {
      category: 'home_appliances',
      mrp: 1199,
      inventory_pct: 50,
      demand_score: 58,
      days_since_listed: 75,
    },
  },
  {
    id: 'ha-002',
    name: 'Vaya Tyffyn Stainless Steel Lunchbox',
    shortDesc: '3-tier tiffin, vacuum-insulated, keeps food hot for 6 hours.',
    category_label: 'Home Appliances',
    imageUrl: IMG.lunchbox,
    rating: 4.7,
    reviewCount: 13200,
    signals: {
      category: 'home_appliances',
      mrp: 1699,
      inventory_pct: 7,           // very low → scarcity premium
      demand_score: 88,           // viral demand
      days_since_listed: 55,
    },
  },

  /* ─── Beauty ───────────────────────────────────────────────────── */
  {
    id: 'be-001',
    name: 'Himalaya Purifying Neem Face Wash 150ml',
    shortDesc: 'Ayurvedic formula, controls oil, prevents pimples, gentle daily use.',
    category_label: 'Beauty',
    imageUrl: IMG.facewash,
    rating: 4.4,
    reviewCount: 95000,
    signals: {
      category: 'beauty',
      mrp: 175,
      inventory_pct: 80,
      demand_score: 60,
      days_since_listed: 15,
    },
  },
  {
    id: 'be-002',
    name: 'Vaseline Lip Therapy Tin 20g',
    shortDesc: 'Petroleum-based lip balm, heals dry and chapped lips overnight.',
    category_label: 'Beauty',
    imageUrl: IMG.lipbalm,
    rating: 4.6,
    reviewCount: 42000,
    signals: {
      category: 'beauty',
      mrp: 125,
      inventory_pct: 90,          // excess → markdown
      demand_score: 45,
      days_since_listed: 200,     // aging
    },
  },
];
