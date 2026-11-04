/**
 * Bete Dires (ቤቴ ድረስ) - Marketplace Front-end Engine
 * Full-featured Alibaba-style search, filtering, order modal, multi-item cart,
 * and Telegram deep linking with psychological risk reduction.
 */

// Global Application State
window.BeteDires = {
  currentLang: localStorage.getItem('betedires_lang') || 'am',
  cart: JSON.parse(localStorage.getItem('betedires_cart') || '[]'),
  selectedItem: null,
  orderQty: 1,
  adminUsername: window.BETE_DIRES_ADMIN || 'BeteDires_admin',
  baseUrl: window.location.origin,
  activeTrendingKeyword: null,
  activeSynonyms: null
};

// Common Ethiopian Marketplace Synonyms
const COMMON_SYNONYMS = {
  'iphone': ['iphone', 'phone', 'samsung', 'ስልክ', 'ሞባይል', 'smartphone'],
  'ስልክ': ['iphone', 'phone', 'samsung', 'ስልክ', 'ሞባይል', 'smartphone'],
  'ሶፋ': ['ሶፋ', 'sofa', 'ሳሎን', 'couch'],
  'sofa': ['ሶፋ', 'sofa', 'ሳሎን', 'couch'],
  'ማቀዝቀዣ': ['ማቀዝቀዣ', 'ፍሪጅ', 'fridge', 'refrigerator'],
  'ፍሪጅ': ['ማቀዝቀዣ', 'ፍሪጅ', 'fridge', 'refrigerator'],
  'fridge': ['ማቀዝቀዣ', 'ፍሪጅ', 'fridge', 'refrigerator'],
  'ጠረጴዛ': ['ጠረጴዛ', 'ጠረፔዛ', 'ጠረንጴዛ', 'table', 'desk'],
  'ጠረፔዛ': ['ጠረጴዛ', 'ጠረፔዛ', 'ጠረንጴዛ', 'table', 'desk'],
  'table': ['ጠረጴዛ', 'ጠረፔዛ', 'ጠረንጴዛ', 'table', 'desk'],
  'desk': ['ጠረጴዛ', 'ጠረፔዛ', 'ጠረንጴዛ', 'table', 'desk']
};

// Bilingual Dictionary for Instant UI Translation
const DICT = {
  am: {
    brandTagline: 'ከአስተማማኝ ሻጮች በቀጥታ ወደ ቤትዎ',
    allCategories: 'ሁሉም ምድቦች',
    allLocations: 'ሁሉም ከተሞች',
    searchPlaceholder: 'እቃዎችን ይፈልጉ...',
    searchBtn: 'ፈልግ',
    trendingLabel: '🔥 ተወዳጅ ቃላት (Trending):',
    orderDirectTelegram: 'ቀጥታ በቴሌግራም አድሚን ይዘዙ',
    cartBtn: 'የተመረጡ እቃዎች',
    payOnDeliveryTitle: 'አይተው ይክፈሉ',
    payOnDeliveryDesc: 'እቃው ቤትዎ ደርሶ በእጅዎ እስኪያዩት እና እስኪፈትሹት ድረስ ክፍያ አይፈጽሙም።',
    directAdminTitle: 'ቀጥታ ከዋና አስተዳዳሪ ጋር',
    directAdminDesc: 'በቴሌግራም ከዋና አስተዳዳሪ ጋር በቀጥታ ይዘዙ። ፈጣን እና አስተማማኝ መልስ።',
    doorstepTitle: 'ቤቴ ድረስ አቅርቦት',
    doorstepDesc: 'አዲስ አበባ፣ ባህር ዳር እና ጎንደር ድረስ በልዩ ሁኔታ እናደርሳለን።',
    verifiedTitle: 'የተረጋገጠ ጥራት እና ሻጭ',
    verifiedDesc: 'እያንዳንዱ እቃ ጥራቱ ተፈትሾ (አዲስ፣ ትንሽ ያገለገለ፣ ያገለገለ) በግልጽ ተቀምጧል።',
    filterTitle: 'ማጣሪያዎች',
    resetFilters: 'ሁሉንም አፅዳ',
    conditionTitle: 'የእቃው ሁኔታ / ጥራት',
    allConditions: 'ሁሉም ሁኔታዎች',
    condNew: 'አዲስ (Brand New)',
    condLikeNew: 'ትንሽ ያገለገለ (Like New)',
    condUsed: 'ያገለገለ (Used)',
    priceRangeTitle: 'የዋጋ ክልል (በብር)',
    allPrices: 'ሁሉም ዋጋዎች',
    under10k: 'ከ 10,000 ብር በታች',
    from10kTo30k: '10,000 - 30,000 ብር',
    from30kTo60k: '30,000 - 60,000 ብር',
    above60k: 'ከ 60,000 ብር በላይ',
    verifiedOnlyLabel: 'የተረጋገጡ ሻጮች ብቻ',
    sortByLabel: 'አደራደር፡',
    sortNewest: 'አዳዲስ እቃዎች',
    sortPriceAsc: 'ዋጋ፡ ከዝቅተኛ ወደ ከፍተኛ',
    sortPriceDesc: 'ዋጋ፡ ከከፍተኛ ወደ ዝቅተኛ',
    showingItems: 'የተገኙ እቃዎች፡',
    buyViaTelegram: 'በቴሌግራም ይዘዙ',
    quickView: 'ዝርዝር',
    doorstepAvailable: 'ቤቴ ድረስ ይደርሳል',
    verifiedSellerBadge: 'የተረጋገጠ ሻጭ',
    emptyTitle: 'ምንም የተገኘ እቃ የለም',
    emptyDesc: 'የፈለጉትን ቃል ቀይረው ይሞክሩ ወይም ማጣሪያዎችን ያፅዱ።',
    modalTitle: 'እቃውን በቴሌግራም ይዘዙ',
    qualityLabel: 'የተመረጠው የእቃ ጥራት / ሁኔታ፡',
    locationLabel: 'የእርስዎ የመላኪያ ቦታ፡',
    selectCityLabel: 'ከተማ ይምረጡ...',
    landmarkPlaceholder: 'ክፍለ ከተማ / ቀበሌ / ሰፈር / ልዩ ቦታ (ምሳሌ፡ ቦሌ መድኃኔዓለም)',
    quantityLabel: 'ብዛት፡',
    optionalPhonePlaceholder: 'የእርስዎ ስልክ ቁጥር (አማራጭ)',
    orderTotalLabel: 'አጠቃላይ የሚከፈል፡',
    completeTelegramBtn: 'ይዘዙ በቴሌግራም (Complete Order on Telegram)',
    guaranteeText: '🔒 እቃውን ቤትዎ ደርሶ አይተው እስኪያረጋግጡ ምንም ቅድመ ክፍያ አይከፍሉም!',
    cartTitle: 'የእርስዎ ትዕዛዝ ዝርዝር',
    cartEmpty: 'ምንም የተመረጠ እቃ የለም።',
    cartCheckoutBtn: 'ሁሉንም እቃዎች በቴሌግራም እዘዝ',
    itemAddedNotice: 'እቃው ወደ ትዕዛዝ ዝርዝር ገብቷል!',
    houseTypeTitle: 'የቤት ዓይነት (Property Type)',
    houseTypeLabel: 'የቤት ዓይነት፡',
    allProperties: 'ሁሉም ቤቶች (All)',
    houseForSale: '🏷️ የሚሸጥ / መግዛት (Buy)',
    houseForRent: '🔑 የሚከራይ / ኪራይ (Rent)',
    mobNavHome: 'መነሻ',
    mobNavCategories: 'ምድቦች',
    mobNavHouse: 'ቤት/ኪራይ'
  },
  en: {
    brandTagline: 'Directly to your doorstep from verified sellers',
    allCategories: 'All Categories',
    allLocations: 'All Cities',
    searchPlaceholder: 'Search products...',
    searchBtn: 'Search',
    trendingLabel: '🔥 Popular Searches (Trending):',
    orderDirectTelegram: 'Order Direct with Telegram Admin',
    cartBtn: 'Order Basket',
    payOnDeliveryTitle: 'Pay on Doorstep Inspection',
    payOnDeliveryDesc: 'Inspect and confirm the product in your hands before making any payment.',
    directAdminTitle: 'Direct Official Admin Contact',
    directAdminDesc: 'Order directly with verified Bete Dires admins on Telegram for instant response.',
    doorstepTitle: 'Doorstep Delivery',
    doorstepDesc: 'Fast doorstep delivery exclusively in Addis Ababa, Bahir Dar, and Gondar.',
    verifiedTitle: 'Verified Quality Guarantee',
    verifiedDesc: 'Every item is cataloged with inspected quality (Brand New, Like New, Gently Used).',
    filterTitle: 'Filters',
    resetFilters: 'Reset All',
    conditionTitle: 'Item Quality / Condition',
    allConditions: 'All Conditions',
    condNew: 'Brand New',
    condLikeNew: 'Like New / Slightly Used',
    condUsed: 'Used',
    priceRangeTitle: 'Price Range (ETB)',
    allPrices: 'All Prices',
    under10k: 'Under 10,000 ETB',
    from10kTo30k: '10,000 - 30,000 ETB',
    from30kTo60k: '30,000 - 60,000 ETB',
    above60k: 'Above 60,000 ETB',
    verifiedOnlyLabel: 'Verified Sellers Only',
    sortByLabel: 'Sort by:',
    sortNewest: 'Newest Arrivals',
    sortPriceAsc: 'Price: Low to High',
    sortPriceDesc: 'Price: High to Low',
    showingItems: 'Showing items:',
    buyViaTelegram: 'Order on Telegram',
    quickView: 'Details',
    doorstepAvailable: 'Doorstep Delivery Available',
    verifiedSellerBadge: 'Verified Seller',
    emptyTitle: 'No items match your criteria',
    emptyDesc: 'Try adjusting your search terms or reset the active filters.',
    modalTitle: 'Order Item via Telegram',
    qualityLabel: 'Confirmed Item Quality / Condition:',
    locationLabel: 'Your Delivery Destination:',
    selectCityLabel: 'Select City...',
    landmarkPlaceholder: 'Sub-city / Kebele / Neighborhood / Landmark (e.g. Bole Medhanialem)',
    quantityLabel: 'Quantity:',
    optionalPhonePlaceholder: 'Your Phone Number (Optional)',
    orderTotalLabel: 'Total Payable at Doorstep:',
    completeTelegramBtn: 'Complete Order on Telegram',
    guaranteeText: '🔒 Zero advance payment risk. You inspect before paying at your door!',
    cartTitle: 'Your Order Basket',
    cartEmpty: 'Your order basket is currently empty.',
    cartCheckoutBtn: 'Order All Items on Telegram',
    itemAddedNotice: 'Item added to your order basket!',
    houseTypeTitle: 'Property Type',
    houseTypeLabel: 'Property Type:',
    allProperties: 'All Properties',
    houseForSale: '🏷️ For Sale (Buy)',
    houseForRent: '🔑 For Rent (Lease)',
    mobNavHome: 'Home',
    mobNavCategories: 'Categories',
    mobNavHouse: 'House/Rent'
  }
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initLanguage();
  initSearchAndFilters();
  initModals();
  initCart();
  renderCartBadge();
  
  // Check if URL has ?item=id or ?order=id to auto-open modal
  const urlParams = new URLSearchParams(window.location.search);
  const autoItemId = urlParams.get('item') || urlParams.get('order');
  if (autoItemId) {
    const targetCard = document.querySelector(`.product-card[data-id="${autoItemId}"]`);
    if (targetCard) {
      openOrderModalFromCard(targetCard);
    }
  }
});

/* ========================================================
   Theme Engine (Dark / Light Mode)
   ======================================================== */
function initTheme() {
  if (window.BeteDiresTheme) {
    window.BeteDiresTheme.updateUI();
  }
}

/* ========================================================
   Language Engine (Amharic / English)
   ======================================================== */
function initLanguage() {
  const currentLang = BeteDires.currentLang;
  applyLanguage(currentLang);

  const langBtn = document.getElementById('lang-toggle-btn');
  if (langBtn) {
    langBtn.addEventListener('click', () => {
      const nextLang = BeteDires.currentLang === 'am' ? 'en' : 'am';
      BeteDires.currentLang = nextLang;
      localStorage.setItem('betedires_lang', nextLang);
      applyLanguage(nextLang);
    });
  }
}

function applyLanguage(lang) {
  const d = DICT[lang] || DICT.am;
  
  // Update toggle button text
  const langText = document.getElementById('current-lang-text');
  if (langText) {
    langText.textContent = lang === 'am' ? 'English (EN)' : 'አማርኛ (AM)';
  }

  // Update translatable elements with data-i18n
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (d[key]) {
      el.textContent = d[key];
    }
  });

  // Update translatable placeholders with data-i18n-placeholder
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.getAttribute('data-i18n-placeholder');
    if (d[key]) {
      el.setAttribute('placeholder', d[key]);
    }
  });

  if (window.BeteDiresTheme) {
    window.BeteDiresTheme.updateUI();
  }
}

/* ========================================================
   Search & Filter Engine
   ======================================================== */
function initSearchAndFilters() {
  const searchInput = document.getElementById('search-input');
  const catSelect = document.getElementById('search-cat-select');
  const locSelect = document.getElementById('search-loc-select');
  const sortSelect = document.getElementById('sort-select');
  const verifiedToggle = document.getElementById('verified-toggle');
  const resetBtn = document.getElementById('reset-filters-btn');
  const emptyResetBtn = document.getElementById('empty-reset-btn');

  // Live filter on inputs
  if (searchInput) {
    searchInput.addEventListener('input', debounce(() => {
      const val = (searchInput.value || '').toLowerCase().trim();
      // Sync active state of keyword quick tags
      document.querySelectorAll('.quick-tag[data-type="keyword"]').forEach(tag => {
        const kw = (tag.getAttribute('data-keyword') || '').toLowerCase();
        const syns = (tag.getAttribute('data-synonyms') || '').toLowerCase();
        if (val && (val === kw || syns.includes(val))) {
          tag.classList.add('active');
        } else {
          tag.classList.remove('active');
        }
      });
      if (!val) {
        window.BeteDires.activeSynonyms = null;
        window.BeteDires.activeTrendingKeyword = null;
      }
      applyFilters();
    }, 250));
  }
  if (catSelect) {
    catSelect.addEventListener('change', () => {
      syncCategoryPills(catSelect.value);
      applyFilters();
    });
  }
  if (locSelect) {
    locSelect.addEventListener('change', () => {
      const currentLoc = locSelect.value;
      // Sync active state of location quick tags
      document.querySelectorAll('.quick-tag[data-type="location"]').forEach(tag => {
        if (tag.getAttribute('data-location') === currentLoc && currentLoc !== 'All') {
          tag.classList.add('active');
        } else {
          tag.classList.remove('active');
        }
      });
      applyFilters();
    });
  }
  if (sortSelect) {
    sortSelect.addEventListener('change', applyFilters);
  }
  if (verifiedToggle) {
    verifiedToggle.addEventListener('change', applyFilters);
  }

  // Category Pills in Ribbon
  document.querySelectorAll('.cat-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      const cat = pill.getAttribute('data-category');
      syncCategoryPills(cat);
      if (catSelect) catSelect.value = cat;
      applyFilters();
    });
  });

  // Quick Trending Tags (Interactive Search & Location Filtering)
  document.querySelectorAll('.quick-tag').forEach(tag => {
    tag.addEventListener('click', (e) => {
      e.preventDefault();
      const type = tag.getAttribute('data-type') || 'keyword';
      const keyword = tag.getAttribute('data-keyword') || '';
      const location = tag.getAttribute('data-location') || '';
      const synonymsRaw = tag.getAttribute('data-synonyms') || '';
      const synonyms = synonymsRaw.toLowerCase().split(',').map(s => s.trim()).filter(Boolean);
      const isAlreadyActive = tag.classList.contains('active');

      if (isAlreadyActive) {
        // Toggle OFF (clear filter)
        tag.classList.remove('active');
        if (type === 'location') {
          if (locSelect) locSelect.value = 'All';
        } else {
          if (searchInput) searchInput.value = '';
          window.BeteDires.activeSynonyms = null;
          window.BeteDires.activeTrendingKeyword = null;
        }
      } else {
        // Toggle ON
        if (type === 'location') {
          // Deactivate other location tags and activate this one
          document.querySelectorAll('.quick-tag[data-type="location"]').forEach(t => t.classList.remove('active'));
          tag.classList.add('active');
          if (locSelect) {
            locSelect.value = location;
          }
        } else {
          // Deactivate other keyword tags and activate this one
          document.querySelectorAll('.quick-tag[data-type="keyword"]').forEach(t => t.classList.remove('active'));
          tag.classList.add('active');
          if (searchInput) {
            searchInput.value = keyword;
          }
          window.BeteDires.activeTrendingKeyword = keyword;
          window.BeteDires.activeSynonyms = synonyms.length > 0 ? synonyms : [keyword.toLowerCase()];
        }
      }

      applyFilters();

      // Smoothly scroll down to products view so user immediately sees results
      const targetView = document.querySelector('.products-header') || document.getElementById('products-grid');
      if (targetView) {
        const topPos = targetView.getBoundingClientRect().top + window.pageYOffset - 85;
        window.scrollTo({ top: Math.max(0, topPos), behavior: 'smooth' });
      }
    });
  });

  // Condition radio filters
  document.querySelectorAll('input[name="filter-condition"]').forEach(radio => {
    radio.addEventListener('change', applyFilters);
  });

  // Price range radio filters
  document.querySelectorAll('input[name="filter-price"]').forEach(radio => {
    radio.addEventListener('change', applyFilters);
  });

  // House Subfilter Pills
  document.querySelectorAll('.house-sub-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      const type = pill.getAttribute('data-house-type') || 'All';
      syncHouseSubPills(type);
      const radio = document.querySelector(`input[name="filter-house-type"][value="${type}"]`);
      if (radio) radio.checked = true;
      applyFilters();
    });
  });

  // House Subfilter Sidebar Radios
  document.querySelectorAll('input[name="filter-house-type"]').forEach(radio => {
    radio.addEventListener('change', (e) => {
      syncHouseSubPills(e.target.value);
      applyFilters();
    });
  });

  // Mobile Bottom Navigation Handlers
  const mobHome = document.getElementById('mob-nav-home');
  const mobCat = document.getElementById('mob-nav-categories');
  const mobHouse = document.getElementById('mob-nav-house');
  const mobCart = document.getElementById('mob-nav-cart');

  if (mobHome) {
    mobHome.addEventListener('click', () => {
      document.querySelectorAll('.mobile-nav-btn').forEach(b => b.classList.remove('active'));
      mobHome.classList.add('active');
      syncCategoryPills('All');
      const catSelect = document.getElementById('search-cat-select');
      if (catSelect) catSelect.value = 'All';
      applyFilters();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  if (mobCat) {
    mobCat.addEventListener('click', () => {
      document.querySelectorAll('.mobile-nav-btn').forEach(b => b.classList.remove('active'));
      mobCat.classList.add('active');
      const ribbon = document.querySelector('.nav-ribbon');
      if (ribbon) ribbon.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  if (mobHouse) {
    mobHouse.addEventListener('click', () => {
      document.querySelectorAll('.mobile-nav-btn').forEach(b => b.classList.remove('active'));
      mobHouse.classList.add('active');
      syncCategoryPills('House/Rent');
      const catSelect = document.getElementById('search-cat-select');
      if (catSelect) catSelect.value = 'House/Rent';
      applyFilters();
      const houseBar = document.getElementById('house-subfilter-bar');
      if (houseBar) houseBar.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  }

  if (mobCart) {
    mobCart.addEventListener('click', () => {
      openCartDrawer();
    });
  }

  // Reset buttons
  if (resetBtn) resetBtn.addEventListener('click', resetAllFilters);
  if (emptyResetBtn) emptyResetBtn.addEventListener('click', resetAllFilters);

  if (catSelect && catSelect.value) {
    syncCategoryPills(catSelect.value);
  }
}

function syncCategoryPills(selectedCat) {
  document.querySelectorAll('.cat-pill').forEach(pill => {
    if (pill.getAttribute('data-category') === selectedCat) {
      pill.classList.add('active');
    } else {
      pill.classList.remove('active');
    }
  });

  const houseSubfilterBar = document.getElementById('house-subfilter-bar');
  const sidebarHouseCard = document.getElementById('sidebar-house-type-card');
  const isHouse = (selectedCat === 'House/Rent');

  if (houseSubfilterBar) {
    houseSubfilterBar.style.display = isHouse ? 'flex' : 'none';
  }
  if (sidebarHouseCard) {
    sidebarHouseCard.style.display = isHouse ? 'block' : 'none';
  }
  if (!isHouse) {
    syncHouseSubPills('All');
    const allRadio = document.querySelector('input[name="filter-house-type"][value="All"]');
    if (allRadio) allRadio.checked = true;
  }
}

function syncHouseSubPills(selectedType) {
  document.querySelectorAll('.house-sub-pill').forEach(pill => {
    if ((pill.getAttribute('data-house-type') || 'All') === selectedType) {
      pill.classList.add('active');
    } else {
      pill.classList.remove('active');
    }
  });
}

function resetAllFilters() {
  const searchInput = document.getElementById('search-input');
  const catSelect = document.getElementById('search-cat-select');
  const locSelect = document.getElementById('search-loc-select');
  const sortSelect = document.getElementById('sort-select');
  const verifiedToggle = document.getElementById('verified-toggle');

  if (searchInput) searchInput.value = '';
  if (catSelect) catSelect.value = 'All';
  if (locSelect) locSelect.value = 'All';
  if (sortSelect) sortSelect.value = 'newest';
  if (verifiedToggle) verifiedToggle.checked = false;

  const defaultCondRadio = document.querySelector('input[name="filter-condition"][value="All"]');
  if (defaultCondRadio) defaultCondRadio.checked = true;

  const defaultPriceRadio = document.querySelector('input[name="filter-price"][value="All"]');
  if (defaultPriceRadio) defaultPriceRadio.checked = true;

  syncHouseSubPills('All');
  const defaultHouseRadio = document.querySelector('input[name="filter-house-type"][value="All"]');
  if (defaultHouseRadio) defaultHouseRadio.checked = true;

  // Deactivate all quick tags and clear active synonyms
  document.querySelectorAll('.quick-tag').forEach(tag => tag.classList.remove('active'));
  window.BeteDires.activeSynonyms = null;
  window.BeteDires.activeTrendingKeyword = null;

  syncCategoryPills('All');
  applyFilters();
}

function applyFilters() {
  const q = (document.getElementById('search-input')?.value || '').toLowerCase().trim();
  const cat = document.getElementById('search-cat-select')?.value || 'All';
  const loc = document.getElementById('search-loc-select')?.value || 'All';
  const sort = document.getElementById('sort-select')?.value || 'newest';
  const verifiedOnly = document.getElementById('verified-toggle')?.checked || false;
  
  const condRadio = document.querySelector('input[name="filter-condition"]:checked');
  const selectedCond = condRadio ? condRadio.value : 'All';

  const priceRadio = document.querySelector('input[name="filter-price"]:checked');
  const selectedPriceRange = priceRadio ? priceRadio.value : 'All';

  const houseTypeRadio = document.querySelector('input[name="filter-house-type"]:checked');
  const selectedHouseType = houseTypeRadio ? houseTypeRadio.value : 'All';

  const cards = Array.from(document.querySelectorAll('.product-card'));
  let visibleCount = 0;

  cards.forEach(card => {
    const title = (card.getAttribute('data-title') || '').toLowerCase();
    const serial = (card.getAttribute('data-serial') || '').toLowerCase();
    const cardCat = card.getAttribute('data-category') || '';
    const cardLoc = (card.getAttribute('data-location') || '').toLowerCase();
    const cardCond = card.getAttribute('data-condition') || '';
    const isVerified = card.getAttribute('data-verified') === '1';
    const rawPrice = parseFloat(card.getAttribute('data-price') || '0');

    // 1. Keyword search (matches title, serial, or location with synonyms)
    let matchesQuery = true;
    if (q) {
      const activeSyns = window.BeteDires.activeSynonyms;
      if (activeSyns && activeSyns.length > 0) {
        matchesQuery = activeSyns.some(term => title.includes(term) || serial.includes(term) || cardLoc.includes(term));
      } else if (COMMON_SYNONYMS[q]) {
        const terms = [q, ...COMMON_SYNONYMS[q]];
        matchesQuery = terms.some(term => title.includes(term) || serial.includes(term) || cardLoc.includes(term));
      } else {
        matchesQuery = title.includes(q) || serial.includes(q) || cardLoc.includes(q);
      }
    }

    // 2. Category match
    let matchesCat = true;
    if (cat !== 'All') {
      matchesCat = (cardCat.toLowerCase() === cat.toLowerCase());
    }

    // 3. Location match (supports English and Amharic city variants)
    let matchesLoc = true;
    if (loc !== 'All') {
      if (loc === 'Addis Ababa') {
        matchesLoc = cardLoc.includes('addis ababa') || cardLoc.includes('አዲስ አበባ') || cardLoc.includes('addis');
      } else if (loc === 'Bahir Dar') {
        matchesLoc = cardLoc.includes('bahir dar') || cardLoc.includes('ባህር ዳር') || cardLoc.includes('bahirdar');
      } else if (loc === 'Gondar') {
        matchesLoc = cardLoc.includes('gondar') || cardLoc.includes('ጎንደር');
      } else {
        matchesLoc = cardLoc.includes(loc.toLowerCase());
      }
    }

    // 4. Condition / Quality match
    let matchesCond = true;
    if (selectedCond !== 'All') {
      matchesCond = cardCond.toLowerCase().includes(selectedCond.toLowerCase());
    }

    // 5. Verified Seller match
    let matchesVerified = true;
    if (verifiedOnly) {
      matchesVerified = isVerified;
    }

    // 6. Price range match
    let matchesPrice = true;
    if (selectedPriceRange === 'under10k') {
      matchesPrice = rawPrice < 10000;
    } else if (selectedPriceRange === '10k-30k') {
      matchesPrice = rawPrice >= 10000 && rawPrice <= 30000;
    } else if (selectedPriceRange === '30k-60k') {
      matchesPrice = rawPrice >= 30000 && rawPrice <= 60000;
    } else if (selectedPriceRange === 'above60k') {
      matchesPrice = rawPrice > 60000;
    }

    // 7. House / Property Type match (Buy vs Rent)
    let matchesHouseType = true;
    if (cat === 'House/Rent' && selectedHouseType !== 'All') {
      const cardHouseType = (card.getAttribute('data-house-type') || 'buy').toLowerCase();
      matchesHouseType = (cardHouseType === selectedHouseType.toLowerCase());
    }

    const isVisible = matchesQuery && matchesCat && matchesLoc && matchesCond && matchesVerified && matchesPrice && matchesHouseType;
    if (isVisible) {
      card.style.display = 'flex';
      visibleCount++;
    } else {
      card.style.display = 'none';
    }
  });

  // Sort visible cards
  const grid = document.getElementById('products-grid');
  if (grid) {
    const visibleCards = cards.filter(c => c.style.display !== 'none');
    visibleCards.sort((a, b) => {
      const priceA = parseFloat(a.getAttribute('data-price') || '0');
      const priceB = parseFloat(b.getAttribute('data-price') || '0');
      const idA = parseInt(a.getAttribute('data-id') || '0', 10);
      const idB = parseInt(b.getAttribute('data-id') || '0', 10);

      if (sort === 'price_asc') return priceA - priceB;
      if (sort === 'price_desc') return priceB - priceA;
      return idB - idA; // newest by default
    });

    visibleCards.forEach(c => grid.appendChild(c));
  }

  // Update visible counter and empty state
  const countDisplay = document.getElementById('results-count-display');
  if (countDisplay) {
    countDisplay.textContent = visibleCount;
  }

  const emptyState = document.getElementById('empty-state-box');
  if (emptyState) {
    emptyState.style.display = (visibleCount === 0) ? 'block' : 'none';
  }
}

/* ========================================================
   Interactive Order Modal & Telegram Integration
   ======================================================== */
function initModals() {
  const modalOverlay = document.getElementById('order-modal-overlay');
  const closeBtn = document.getElementById('modal-close-btn');
  const qtyMinusBtn = document.getElementById('qty-minus-btn');
  const qtyPlusBtn = document.getElementById('qty-plus-btn');
  const orderSubmitBtn = document.getElementById('modal-submit-telegram-btn');

  // Close modal on click outside or escape key
  if (modalOverlay) {
    modalOverlay.addEventListener('click', (e) => {
      if (e.target === modalOverlay) closeOrderModal();
    });
  }
  if (closeBtn) {
    closeBtn.addEventListener('click', closeOrderModal);
  }
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeOrderModal();
      closeCartDrawer();
    }
  });

  // Quantity controls
  if (qtyMinusBtn) {
    qtyMinusBtn.addEventListener('click', () => {
      if (BeteDires.orderQty > 1) {
        BeteDires.orderQty--;
        updateOrderModalCalc();
      }
    });
  }
  if (qtyPlusBtn) {
    qtyPlusBtn.addEventListener('click', () => {
      BeteDires.orderQty++;
      updateOrderModalCalc();
    });
  }

  // City selector change auto-fills default
  const citySelect = document.getElementById('order-city-select');
  if (citySelect) {
    citySelect.addEventListener('change', updateOrderModalCalc);
  }

  // Wire up Card Buy buttons
  document.querySelectorAll('.buy-telegram-btn, .quick-view-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const card = btn.closest('.product-card');
      if (card) {
        openOrderModalFromCard(card);
      }
    });
  });

  // Wire up Submit Order button
  if (orderSubmitBtn) {
    orderSubmitBtn.addEventListener('click', handleOrderModalSubmit);
  }
}

function openOrderModalFromCard(card) {
  const id = card.getAttribute('data-id');
  const title = card.getAttribute('data-title');
  const serial = card.getAttribute('data-serial');
  const price = card.getAttribute('data-price');
  const condition = card.getAttribute('data-condition');
  const location = card.getAttribute('data-location');
  const imgUrl = card.querySelector('.card-img')?.getAttribute('src') || '/static/placeholder.svg';

  BeteDires.selectedItem = {
    id,
    title,
    serial,
    price: parseFloat(price) || 0,
    condition,
    location,
    imgUrl
  };
  BeteDires.orderQty = 1;

  // Populate Modal Fields
  document.getElementById('modal-img').src = imgUrl;
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-serial').textContent = `Serial: #${serial}`;
  document.getElementById('modal-unit-price').textContent = `${formatBirr(BeteDires.selectedItem.price)} ብር / ETB`;
  
  const qualityBadge = document.getElementById('modal-quality-badge');
  if (qualityBadge) {
    qualityBadge.textContent = condition;
    if (condition.toLowerCase().includes('new') || condition.includes('አዲስ')) {
      qualityBadge.className = 'quality-tag-badge cond-new';
    } else if (condition.toLowerCase().includes('slightly') || condition.includes('ትንሽ')) {
      qualityBadge.className = 'quality-tag-badge cond-like-new';
    } else {
      qualityBadge.className = 'quality-tag-badge cond-used';
    }
  }

  // Auto-detect matching city if present in item location (Addis Ababa, Bahir Dar, Gondar)
  const citySelect = document.getElementById('order-city-select');
  if (citySelect) {
    const locLower = (location || '').toLowerCase();
    if (locLower.includes('bahir') || locLower.includes('ባህር')) citySelect.value = 'Bahir Dar';
    else if (locLower.includes('gondar') || locLower.includes('ጎንደር')) citySelect.value = 'Gondar';
    else citySelect.value = 'Addis Ababa';
  }

  updateOrderModalCalc();

  // Open Modal
  const modalOverlay = document.getElementById('order-modal-overlay');
  if (modalOverlay) {
    modalOverlay.classList.add('open');
  }
}

function updateOrderModalCalc() {
  if (!BeteDires.selectedItem) return;
  const qtyDisplay = document.getElementById('modal-qty-display');
  const totalDisplay = document.getElementById('modal-total-amount');

  if (qtyDisplay) qtyDisplay.textContent = BeteDires.orderQty;
  if (totalDisplay) {
    const total = BeteDires.selectedItem.price * BeteDires.orderQty;
    totalDisplay.textContent = `${formatBirr(total)} ብር`;
  }
}

function closeOrderModal() {
  const modalOverlay = document.getElementById('order-modal-overlay');
  if (modalOverlay) {
    modalOverlay.classList.remove('open');
  }
  BeteDires.selectedItem = null;
}

/**
 * Constructs clean, pre-filled Telegram message with Item, Quality, and Location
 * and connects customer directly to the admin on Telegram.
 */
function handleOrderModalSubmit() {
  if (!BeteDires.selectedItem) return;

  const item = BeteDires.selectedItem;
  const city = document.getElementById('order-city-select')?.value || 'Addis Ababa';
  const landmark = document.getElementById('order-landmark-input')?.value.trim() || '';
  const phone = document.getElementById('order-phone-input')?.value.trim() || '';
  const qty = BeteDires.orderQty;
  const total = item.price * qty;

  const fullLocation = landmark ? `${city}, ${landmark}` : city;
  const itemUrl = `${window.location.origin}/item/${item.id}`;

  // Structured Telegram Message (High Psychology & Respectful Commercial Etiquette)
  const tgMessage = 
`👋 ሰላም Bete Dires Admin! በድረ-ገጹ (Website) በኩል እቃ ማዘዝ እፈልጋለሁ፡

📦 እቃ (Item): ${item.title}
🏷 መለያ ቁጥር (Serial): #${item.serial}
✨ ጥራት / ሁኔታ (Quality): ${item.condition}
💰 ዋጋ (Unit Price): ${formatBirr(item.price)} ብር
🔢 ብዛት (Quantity): ${qty}
💵 አጠቃላይ ድምር (Total): ${formatBirr(total)} ብር
📍 የመላኪያ ቦታ (Location): ${fullLocation}
${phone ? `📞 ስልክ (Phone): ${phone}\n` : ''}🔗 የምርት ሊንክ (Link): ${itemUrl}

እባክዎን ትዕዛዜን አረጋግጠው የመላኪያ ሰዓት ይንገሩኝ። አመሰግናለሁ!`;

  // Asynchronously record order in backend database
  fetch('/api/order', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      item_id: parseInt(item.id, 10),
      item_name: item.title,
      item_serial: item.serial,
      item_quality: item.condition,
      quantity: qty,
      total_price: `${formatBirr(total)} ብር`,
      customer_city: city,
      customer_location: fullLocation,
      customer_phone: phone,
      customer_note: `Web Direct Order for #${item.serial}`
    })
  }).catch(err => console.log('Order log notification dispatched:', err));

  // Construct Telegram Deep Link
  const adminHandle = (BeteDires.adminUsername || 'BeteDires_admin').replace('@', '');
  const tgUrl = `https://t.me/${adminHandle}?text=${encodeURIComponent(tgMessage)}`;

  // Launch Telegram chat in new window
  window.open(tgUrl, '_blank');
  closeOrderModal();
}

/* ========================================================
   Multi-Item Shopping Cart Drawer
   ======================================================== */
function initCart() {
  const cartBtn = document.getElementById('cart-header-btn');
  const mobileCartBtn = document.getElementById('floating-cart-bubble');
  const closeCartBtn = document.getElementById('close-cart-btn');
  const cartOverlay = document.getElementById('cart-drawer-overlay');
  const checkoutBtn = document.getElementById('cart-checkout-btn');

  // Open Cart Drawer
  if (cartBtn) cartBtn.addEventListener('click', openCartDrawer);
  if (mobileCartBtn) mobileCartBtn.addEventListener('click', openCartDrawer);
  
  // Close Cart Drawer
  if (closeCartBtn) closeCartBtn.addEventListener('click', closeCartDrawer);
  if (cartOverlay) {
    cartOverlay.addEventListener('click', (e) => {
      if (e.target === cartOverlay) closeCartDrawer();
    });
  }

  // Wire up Add-To-Cart buttons on cards
  document.querySelectorAll('.add-cart-icon-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const card = btn.closest('.product-card');
      if (card) {
        addToCartFromCard(card);
      }
    });
  });

  // Batch Checkout on Telegram
  if (checkoutBtn) {
    checkoutBtn.addEventListener('click', handleBatchCartCheckout);
  }
}

function addToCartFromCard(card) {
  const id = card.getAttribute('data-id');
  const title = card.getAttribute('data-title');
  const serial = card.getAttribute('data-serial');
  const price = parseFloat(card.getAttribute('data-price') || '0');
  const condition = card.getAttribute('data-condition');
  const imgUrl = card.querySelector('.card-img')?.getAttribute('src') || '/static/placeholder.svg';

  const existingIndex = BeteDires.cart.findIndex(i => i.id === id);
  if (existingIndex > -1) {
    BeteDires.cart[existingIndex].qty++;
  } else {
    BeteDires.cart.push({
      id,
      title,
      serial,
      price,
      condition,
      imgUrl,
      qty: 1
    });
  }

  saveCart();
  renderCartBadge();
  renderCartItems();

  // Toast animation on button
  const originalHtml = card.querySelector('.add-cart-icon-btn').innerHTML;
  card.querySelector('.add-cart-icon-btn').innerHTML = '✓';
  card.querySelector('.add-cart-icon-btn').style.background = '#10b981';
  card.querySelector('.add-cart-icon-btn').style.color = '#ffffff';
  setTimeout(() => {
    card.querySelector('.add-cart-icon-btn').innerHTML = originalHtml;
    card.querySelector('.add-cart-icon-btn').style.background = '';
    card.querySelector('.add-cart-icon-btn').style.color = '';
  }, 1000);
}

function saveCart() {
  localStorage.setItem('betedires_cart', JSON.stringify(BeteDires.cart));
}

function renderCartBadge() {
  const count = BeteDires.cart.reduce((sum, item) => sum + item.qty, 0);
  const badge = document.getElementById('cart-badge-count');
  const mobileCount = document.getElementById('mobile-cart-count');
  
  if (badge) badge.textContent = count;
  if (mobileCount) mobileCount.textContent = count;
  const mobNavCount = document.getElementById('mob-nav-cart-count');
  if (mobNavCount) mobNavCount.textContent = count;
}

function openCartDrawer() {
  renderCartItems();
  const drawerOverlay = document.getElementById('cart-drawer-overlay');
  if (drawerOverlay) {
    drawerOverlay.classList.add('open');
  }
}

function closeCartDrawer() {
  const drawerOverlay = document.getElementById('cart-drawer-overlay');
  if (drawerOverlay) {
    drawerOverlay.classList.remove('open');
  }
}

function renderCartItems() {
  const listContainer = document.getElementById('cart-items-list');
  const totalDisplay = document.getElementById('cart-drawer-total');
  if (!listContainer) return;

  if (BeteDires.cart.length === 0) {
    listContainer.innerHTML = `
      <div style="text-align: center; padding: 40px 10px; color: #94a3b8;">
        <svg style="width: 48px; height: 48px; margin-bottom: 12px; fill: none; stroke: currentColor;" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z"/>
        </svg>
        <p style="font-weight: 600;">${DICT[BeteDires.currentLang].cartEmpty}</p>
      </div>
    `;
    if (totalDisplay) totalDisplay.textContent = '0 ብር';
    return;
  }

  let totalSum = 0;
  listContainer.innerHTML = '';

  BeteDires.cart.forEach((item, index) => {
    const itemTotal = item.price * item.qty;
    totalSum += itemTotal;

    const row = document.createElement('div');
    row.className = 'cart-item-row';
    row.innerHTML = `
      <img src="${item.imgUrl}" class="cart-item-thumb" onerror="this.src='/static/placeholder.svg'" alt="">
      <div class="cart-item-details">
        <h4 class="cart-item-title">${item.title}</h4>
        <div class="cart-item-meta">#${item.serial} • ${item.condition}</div>
        <div class="cart-item-price">${formatBirr(itemTotal)} ብር <span style="font-size: 11px; font-weight: normal; color: #64748b;">(${formatBirr(item.price)} x ${item.qty})</span></div>
      </div>
      <button class="cart-item-remove-btn" data-index="${index}" title="Remove item">✕</button>
    `;

    row.querySelector('.cart-item-remove-btn').addEventListener('click', () => {
      BeteDires.cart.splice(index, 1);
      saveCart();
      renderCartBadge();
      renderCartItems();
    });

    listContainer.appendChild(row);
  });

  if (totalDisplay) {
    totalDisplay.textContent = `${formatBirr(totalSum)} ብር`;
  }
}

function handleBatchCartCheckout() {
  if (BeteDires.cart.length === 0) return;

  const city = document.getElementById('cart-city-select')?.value || 'Addis Ababa';
  const landmark = document.getElementById('cart-landmark-input')?.value.trim() || '';
  const fullLocation = landmark ? `${city}, ${landmark}` : city;

  let totalSum = 0;
  let itemsListText = '';

  BeteDires.cart.forEach((it, idx) => {
    const sub = it.price * it.qty;
    totalSum += sub;
    itemsListText += `${idx + 1}. ${it.title} (#${it.serial})\n   ✨ ጥራት (Quality): ${it.condition}\n   💰 ዋጋ: ${formatBirr(sub)} ብር (${formatBirr(it.price)} x ${it.qty})\n\n`;
  });

  const tgMessage = 
`👋 ሰላም Bete Dires Admin! በድረ-ገጹ (Website) በኩል የተመረጡ እቃዎችን ማዘዝ እፈልጋለሁ፡

🛒 የተመረጡ እቃዎች ዝርዝር (Items):
${itemsListText}━━━━━━━━━━━━━━━━━━━
💵 አጠቃላይ ድምር (Total Sum): ${formatBirr(totalSum)} ብር
📍 የመላኪያ ቦታ (Delivery Location): ${fullLocation}

እባክዎን ትዕዛዜን አረጋግጠው የመላኪያ ሰዓት ይንገሩኝ። አመሰግናለሁ!`;

  // Log batch order to backend
  fetch('/api/order', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      item_name: `Batch Order (${BeteDires.cart.length} items)`,
      quantity: BeteDires.cart.reduce((s, i) => s + i.qty, 0),
      total_price: `${formatBirr(totalSum)} ብር`,
      customer_city: city,
      customer_location: fullLocation,
      customer_note: `Multi-item order: ${BeteDires.cart.map(i => `#${i.serial}`).join(', ')}`
    })
  }).catch(e => console.log(e));

  const adminHandle = (BeteDires.adminUsername || 'BeteDires_admin').replace('@', '');
  const tgUrl = `https://t.me/${adminHandle}?text=${encodeURIComponent(tgMessage)}`;

  window.open(tgUrl, '_blank');
  closeCartDrawer();
}

/* ========================================================
   Helpers
   ======================================================== */
function formatBirr(amount) {
  if (isNaN(amount)) return '0';
  return Number(amount).toLocaleString('en-US');
}

function debounce(fn, delay) {
  let timer = null;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}
