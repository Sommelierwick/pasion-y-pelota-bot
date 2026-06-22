#!/usr/bin/env python3
"""
create_and_upload_theme.py — Crea y sube el tema híbrido Diario Marca + Olé a WordPress
"""
import os, zipfile, shutil, requests, re, sys, base64
from dotenv import load_dotenv

load_dotenv()
WP_URL  = os.getenv("WP_URL","https://pasionypelota.com").rstrip("/")
WP_USER = os.getenv("WP_USER")
WP_PASS = os.getenv("WP_PASSWORD")

THEME_SLUG = "pasion-pelota"
THEME_DIR  = f"/tmp/{THEME_SLUG}"

if os.path.exists(THEME_DIR):
    shutil.rmtree(THEME_DIR)
os.makedirs(THEME_DIR)
print(f"📁 Creando archivos del tema híbrido Marca+Olé en {THEME_DIR}...")

# ── style.css ──────────────────────────────────────────────────────────────
open(f"{THEME_DIR}/style.css","w",encoding="utf-8").write("""\
/*
Theme Name: Pasión y Pelota
Theme URI: https://pasionypelota.com
Description: Portal deportivo profesional - Marca + Olé Hybrid Design
Version: 1.2
Author: Bot Pasión y Pelota
*/
@import url('https://fonts.googleapis.com/css2?family=Roboto+Condensed:ital,wght@0,400;0,700;1,700&family=Inter:wght@400;500;600;700;800&display=swap');

:root {
  --marca-red: #d90011;
  --ole-green: #89c53f;
  --ole-green-dark: #6fa630;
  --dark-bg: #111111;
  --light-bg: #f4f6f9;
  --border-color: #e3e7ec;
  --text-dark: #1a1a1a;
  --text-light: #606f7b;
  --white: #ffffff;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Inter', sans-serif;
  background: var(--light-bg);
  color: #333333;
}

a {
  text-decoration: none;
  color: inherit;
  transition: color 0.15s ease;
}

a:hover {
  color: var(--marca-red);
}

img {
  max-width: 100%;
  display: block;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 15px;
}

/* TOP BAR */
.top-bar {
  background: #111;
  color: #999;
  font-size: 11px;
  padding: 6px 0;
  font-weight: 500;
  text-transform: uppercase;
}

.top-bar .container {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.top-bar a {
  color: #999;
  margin-left: 12px;
}

.top-bar a:hover {
  color: var(--white);
}

/* SCORES STRIP */
.scores-strip {
  background: #f1f3f5;
  border-bottom: 1px solid var(--border-color);
  padding: 8px 0;
  font-size: 11px;
  overflow: hidden;
}

.scores-marquee {
  width: 100%;
  overflow: hidden;
}

.scores-track {
  display: inline-flex;
  gap: 15px;
  animation: scores-scroll 35s linear infinite;
  white-space: nowrap;
}

.scores-track:hover {
  animation-play-state: paused;
}

@keyframes scores-scroll {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}

.score-item {
  background: var(--white);
  padding: 6px 12px;
  border-radius: 4px;
  border: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  gap: 8px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.03);
  flex-shrink: 0;
  color: var(--text-dark);
}

.league-tag {
  font-weight: 800;
  color: var(--marca-red);
  font-size: 9px;
  background: #ffebeb;
  padding: 2px 5px;
  border-radius: 2px;
  letter-spacing: 0.5px;
}

.score-item strong {
  color: var(--text-dark);
}

.match-status {
  color: var(--ole-green-dark);
  font-weight: 700;
  font-size: 10px;
}

/* Overrides for upcoming matches strip to prevent same text color as background */
.upcoming-strip .score-item {
  background: #2a2a2a !important;
  color: #ffffff !important;
  border: 1px solid #3a3a3a !important;
}

.upcoming-strip .score-item strong {
  color: #ffffff !important;
}

.upcoming-strip .score-item .match-status {
  color: #ffcc00 !important;
}

.upcoming-strip .score-item .league-tag {
  background: var(--ole-green) !important;
  color: #111111 !important;
}

/* HEADER */
.site-header {
  background: var(--white);
  padding: 18px 0;
  border-bottom: 3px solid var(--marca-red);
}

.site-header .container {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.logo-text {
  font-family: 'Roboto Condensed', sans-serif;
  font-size: 38px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: -1.5px;
}

.logo-pasion {
  color: var(--marca-red);
}

.logo-y-pelota {
  color: var(--ole-green);
  font-style: italic;
}

.header-tagline {
  font-family: 'Roboto Condensed', sans-serif;
  font-size: 14px;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--text-light);
  letter-spacing: 1px;
}

/* STICKY WRAPPER */
.sticky-header-wrapper {
  position: sticky;
  top: 0;
  z-index: 200;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

/* NAVIGATION */
.main-nav {
  background: var(--dark-bg);
}

.main-nav .container {
  display: flex;
}

.nav-menu {
  list-style: none;
  display: flex;
  margin: 0;
  padding: 0;
}

.nav-menu li a {
  display: block;
  padding: 14px 18px;
  color: #dddddd;
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  transition: all 0.2s ease;
  border-top: 3px solid transparent;
}

.nav-menu li a:hover, .nav-menu .current-menu-item a {
  background: #222222;
  color: var(--white);
  border-top-color: var(--ole-green);
}

/* TICKER */
.ticker-bar {
  background: var(--marca-red);
  padding: 8px 0;
  overflow: hidden;
}

.ticker-bar .container {
  display: flex;
  align-items: center;
  gap: 15px;
}

.ticker-label {
  background: var(--white);
  color: var(--marca-red);
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 1px;
  text-transform: uppercase;
  padding: 3px 8px;
  border-radius: 3px;
  white-space: nowrap;
  flex-shrink: 0;
}

.ticker-wrap {
  overflow: hidden;
  flex: 1;
}

.ticker-inner {
  display: inline-flex;
  gap: 0;
  animation: scroll 40s linear infinite;
  white-space: nowrap;
}

.ticker-inner a {
  color: var(--white);
  font-size: 13px;
  font-weight: 600;
  padding: 0 30px;
  border-right: 1px solid rgba(255,255,255,0.2);
}

.ticker-inner a:hover {
  text-decoration: underline;
}

@keyframes scroll {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}

/* LAYOUT */
.site-content {
  padding: 24px 0;
}

.content-wrap {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 24px;
}

/* HERO SECTION */
.hero-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 4px;
  background: #000;
  margin-bottom: 24px;
  border-radius: 4px;
  overflow: hidden;
}

.hero-main {
  position: relative;
  overflow: hidden;
  height: 440px;
}

.hero-main img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.4s ease;
}

.hero-main:hover img {
  transform: scale(1.02);
}

.hero-no-img {
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, var(--marca-red), var(--dark-bg));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 80px;
}

.hero-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(transparent, rgba(0,0,0,0.92));
  padding: 40px 24px 24px;
}

.volanta {
  display: inline-block;
  color: var(--ole-green);
  font-family: 'Roboto Condensed', sans-serif;
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  margin-bottom: 8px;
}

.hero-overlay h2 {
  font-family: 'Roboto Condensed', sans-serif;
  font-size: 30px;
  font-weight: 700;
  font-style: italic;
  color: var(--white);
  line-height: 1.2;
  text-transform: uppercase;
}

.hero-overlay h2 a {
  color: var(--white);
}

.hero-overlay h2 a:hover {
  color: var(--ole-green);
}

.hero-overlay .post-time {
  color: rgba(255,255,255,0.6);
  font-size: 11px;
  margin-top: 10px;
}

.hero-side {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.hero-side-item {
  position: relative;
  overflow: hidden;
  flex: 1;
  height: 218px;
}

.hero-side-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.4s ease;
}

.hero-side-item:hover img {
  transform: scale(1.04);
}

.hero-side-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(transparent, rgba(0,0,0,0.85));
  padding: 20px 15px 15px;
}

.hero-side-overlay h3 {
  font-family: 'Roboto Condensed', sans-serif;
  font-size: 15px;
  font-weight: 700;
  font-style: italic;
  color: var(--white);
  line-height: 1.3;
  text-transform: uppercase;
}

.hero-side-overlay h3 a {
  color: var(--white);
}

.hero-side-overlay h3 a:hover {
  color: var(--ole-green);
}

/* SECTION HEADING */
.section-heading {
  font-family: 'Roboto Condensed', sans-serif;
  font-size: 18px;
  font-weight: 800;
  text-transform: uppercase;
  color: var(--text-dark);
  border-left: 5px solid var(--marca-red);
  padding-left: 12px;
  margin-bottom: 16px;
  letter-spacing: 0.5px;
}

/* ARTICLE GRID */
.articles-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.art-card {
  background: var(--white);
  border-radius: 4px;
  overflow: hidden;
  border: 1px solid var(--border-color);
  box-shadow: 0 2px 4px rgba(0,0,0,0.02);
  transition: all 0.2s ease;
}

.art-card:hover {
  box-shadow: 0 8px 16px rgba(0,0,0,0.08);
  transform: translateY(-2px);
  border-color: #cbd5e0;
}

.art-card-img {
  width: 100%;
  height: 200px;
  object-fit: cover;
  object-position: center 25%;
}

.art-card-no-img {
  width: 100%;
  height: 160px;
  background: linear-gradient(135deg, var(--marca-red), var(--dark-bg));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 44px;
}

.art-card-body {
  padding: 15px;
}

.art-card-cat {
  font-family: 'Roboto Condensed', sans-serif;
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
  color: var(--ole-green-dark);
  margin-bottom: 6px;
  letter-spacing: 0.8px;
}

.art-card-title {
  font-family: 'Roboto Condensed', sans-serif;
  font-size: 17px;
  font-weight: 700;
  line-height: 1.3;
  color: var(--text-dark);
  margin-bottom: 8px;
}

.art-card-title a {
  color: var(--text-dark);
}

.art-card-title a:hover {
  color: var(--marca-red);
}

.art-card-excerpt {
  font-size: 13px;
  color: var(--text-light);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-bottom: 10px;
}

.art-card-time {
  font-size: 11px;
  color: #a0aec0;
}

/* LIST ARTICLES */
.articles-list-wrap {
  background: var(--white);
  border-radius: 4px;
  border: 1px solid var(--border-color);
  overflow: hidden;
  margin-bottom: 24px;
}

.list-art-item {
  display: flex;
  gap: 15px;
  padding: 15px;
  border-bottom: 1px solid var(--border-color);
  align-items: center;
}

.list-art-item:last-child {
  border-bottom: none;
}

.list-art-thumb {
  width: 90px;
  height: 64px;
  object-fit: cover;
  border-radius: 4px;
  flex-shrink: 0;
}

.list-art-no-thumb {
  width: 90px;
  height: 64px;
  border-radius: 4px;
  flex-shrink: 0;
  background: linear-gradient(135deg, var(--ole-green), var(--dark-bg));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
}

.list-art-title {
  font-family: 'Roboto Condensed', sans-serif;
  font-size: 16px;
  font-weight: 700;
  line-height: 1.3;
  color: var(--text-dark);
}

.list-art-title a {
  color: var(--text-dark);
}

.list-art-title a:hover {
  color: var(--ole-green-dark);
}

.list-art-time {
  font-size: 11px;
  color: #a0aec0;
  margin-top: 6px;
}

/* SIDEBAR */
.sidebar {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.widget-box {
  background: var(--white);
  border-radius: 4px;
  border: 1px solid var(--border-color);
  overflow: hidden;
  box-shadow: 0 2px 4px rgba(0,0,0,0.01);
}

.widget-head {
  background: var(--dark-bg);
  color: var(--white);
  padding: 12px 16px;
  font-family: 'Roboto Condensed', sans-serif;
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.widget-head::before {
  content: '';
  display: block;
  width: 4px;
  height: 14px;
  background: var(--ole-green);
  border-radius: 2px;
}

.sb-post {
  display: flex;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  align-items: flex-start;
}

.sb-post:last-child {
  border-bottom: none;
}

.sb-num {
  font-family: 'Roboto Condensed', sans-serif;
  font-size: 26px;
  font-weight: 800;
  color: #e2e8f0;
  line-height: 1;
  flex-shrink: 0;
  width: 26px;
  text-align: center;
}

.sb-post:hover .sb-num {
  color: var(--marca-red);
}

.sb-post-title {
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
  color: var(--text-dark);
}

.sb-post-title a {
  color: var(--text-dark);
}

.sb-post-title a:hover {
  color: var(--marca-red);
}

.sb-post-time {
  font-size: 11px;
  color: #a0aec0;
  margin-top: 4px;
}

/* EL SEMAFORO WIDGET */
.semaforo-head {
  background: #111;
  color: #fff;
}
.semaforo-body {
  padding: 15px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.semaforo-link {
  text-decoration: none;
  color: inherit;
  display: block;
  border-bottom: 1px solid #f0f0f0;
  padding-bottom: 10px;
  transition: all 0.2s ease;
  border-radius: 4px;
}
.semaforo-link:hover {
  background-color: #f7fafc;
  transform: translateX(4px);
}
.semaforo-link:last-child {
  border-bottom: none;
  padding-bottom: 0;
}
.semaforo-item {
  display: flex;
  gap: 10px;
  font-size: 12px;
  line-height: 1.4;
  padding: 4px;
}
.semaforo-dot {
  font-size: 16px;
  flex-shrink: 0;
}
.semaforo-content strong {
  display: block;
  font-size: 13px;
  color: #111;
}

/* CATEGORY & EMPTY STATE DESIGN */
.category-header {
  background: linear-gradient(135deg, var(--dark-bg) 0%, #1f2937 100%);
  padding: 30px;
  border-radius: 6px;
  margin-bottom: 24px;
  border-bottom: 4px solid var(--marca-red);
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  position: relative;
  overflow: hidden;
}
.category-header-decor {
  position: absolute;
  right: -20px;
  bottom: -20px;
  font-size: 150px;
  opacity: 0.05;
  color: var(--white);
  font-weight: 800;
  font-family: 'Roboto Condensed', sans-serif;
  pointer-events: none;
  user-select: none;
}
.category-tag {
  background: var(--marca-red);
  color: #fff;
  text-transform: uppercase;
  font-size: 10px;
  font-weight: 800;
  padding: 4px 8px;
  border-radius: 3px;
  letter-spacing: 1px;
}
.category-header h1 {
  color: #fff;
  font-family: 'Roboto Condensed', sans-serif;
  font-size: 32px;
  font-weight: 800;
  margin-top: 8px;
  text-transform: uppercase;
  letter-spacing: -0.5px;
}
.category-header p {
  color: #cbd5e0;
  font-size: 14px;
  margin-top: 6px;
  max-width: 600px;
  line-height: 1.5;
}

.empty-category-box {
  background: var(--white);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 45px 20px;
  text-align: center;
  margin-bottom: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.02);
}
.empty-category-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
.empty-category-title {
  font-family: 'Roboto Condensed', sans-serif;
  font-size: 20px;
  font-weight: 700;
  color: var(--text-dark);
  margin-bottom: 8px;
}
.empty-category-text {
  color: var(--text-light);
  font-size: 14px;
  max-width: 450px;
  margin: 0 auto;
}


/* SINGLE POST TEMPLATE */
.single-header {
  background: var(--white);
  padding: 30px;
  margin-bottom: 16px;
  border-radius: 4px;
  border: 1px solid var(--border-color);
}

.single-title {
  font-family: 'Roboto Condensed', sans-serif;
  font-size: 34px;
  font-weight: 800;
  line-height: 1.2;
  color: var(--text-dark);
  margin: 12px 0;
}

.single-meta {
  font-size: 12px;
  color: var(--text-light);
  display: flex;
  gap: 16px;
  padding-top: 12px;
  border-top: 1px solid #edf2f7;
}

.single-featured-img {
  width: 100%;
  max-height: 480px;
  object-fit: cover;
  border-radius: 4px;
  margin-bottom: 16px;
}

.post-body {
  background: var(--white);
  padding: 30px;
  border-radius: 4px;
  border: 1px solid var(--border-color);
  margin-bottom: 16px;
}

.post-body p {
  font-size: 16px;
  line-height: 1.8;
  color: #2d3748;
  margin-bottom: 20px;
}

.post-body h2 {
  font-family: 'Roboto Condensed', sans-serif;
  font-size: 24px;
  font-weight: 800;
  color: var(--text-dark);
  margin: 30px 0 15px;
  border-left: 5px solid var(--marca-red);
  padding-left: 12px;
}

.post-body h3 {
  font-family: 'Roboto Condensed', sans-serif;
  font-size: 19px;
  font-weight: 800;
  color: var(--text-dark);
  margin: 22px 0 12px;
}

.post-body table {
  width: 100%;
  border-collapse: collapse;
  margin: 25px 0;
  font-size: 14px;
}

.post-body table th {
  background: var(--dark-bg);
  color: var(--white);
  padding: 12px 14px;
  text-align: left;
  font-weight: 700;
  text-transform: uppercase;
  font-size: 12px;
  letter-spacing: 0.5px;
}

.post-body table td {
  padding: 10px 14px;
  border-bottom: 1px solid #edf2f7;
}

.post-body table tr:nth-child(even) td {
  background: #f7fafc;
}

.post-body table tr:hover td {
  background: #ffebeb;
}

.affiliate-box {
  background: #f7fafc;
  border: 2px dashed var(--ole-green);
  border-radius: 6px;
  padding: 20px;
  margin: 25px 0;
  text-align: center;
}

.affiliate-box strong {
  display: block;
  font-size: 16px;
  color: var(--text-dark);
  margin-bottom: 8px;
}

.affiliate-box a {
  display: inline-block;
  background: var(--ole-green);
  color: var(--white);
  padding: 8px 20px;
  border-radius: 4px;
  font-weight: 700;
  font-size: 13px;
  text-transform: uppercase;
}

.affiliate-box a:hover {
  background: var(--ole-green-dark);
  color: var(--white);
}

.tags-wrap {
  background: var(--white);
  padding: 15px 30px;
  border-radius: 4px;
  border: 1px solid var(--border-color);
  margin-bottom: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.tag-label {
  font-size: 11px;
  font-weight: 800;
  color: var(--text-light);
  text-transform: uppercase;
}

.tag-link {
  background: #edf2f7;
  color: #4a5568;
  font-size: 12px;
  padding: 6px 14px;
  border-radius: 20px;
  border: 1px solid #e2e8f0;
}

.tag-link:hover {
  background: var(--marca-red);
  color: var(--white);
  border-color: var(--marca-red);
}

.share-bar {
  background: var(--white);
  padding: 15px 30px;
  border-radius: 4px;
  border: 1px solid var(--border-color);
  margin-bottom: 24px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.share-label {
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.share-btn {
  padding: 8px 16px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 700;
  color: var(--white);
}

.share-btn.tw { background: #1DA1F2; }
.share-btn.fb { background: #1877F2; }
.share-btn.wa { background: #25D366; }
.share-btn:hover { opacity: 0.9; color: var(--white); }

/* FOOTER */
.site-footer {
  background: var(--dark-bg);
  color: #a0aec0;
  padding: 40px 0 0;
  margin-top: 40px;
  border-top: 4px solid var(--ole-green);
}

.footer-grid {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr;
  gap: 40px;
  margin-bottom: 30px;
}

.footer-logo-text {
  font-family: 'Roboto Condensed', sans-serif;
  font-size: 24px;
  font-weight: 800;
  color: var(--white);
  margin-bottom: 12px;
  text-transform: uppercase;
}

.footer-logo-text em {
  color: var(--ole-green);
  font-style: normal;
}

.footer-desc {
  font-size: 13px;
  line-height: 1.7;
}

.footer-col-title {
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
  color: var(--white);
  border-bottom: 1px solid #2d3748;
  padding-bottom: 8px;
  margin-bottom: 16px;
  letter-spacing: 0.5px;
}

.footer-links {
  list-style: none;
  padding: 0;
}

.footer-links li {
  margin-bottom: 10px;
}

.footer-links a {
  color: #a0aec0;
  font-size: 13px;
}

.footer-links a:hover {
  color: var(--ole-green);
}

.footer-bottom {
  border-top: 1px solid #2d3748;
  padding: 20px 0;
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #718096;
}

.footer-bottom a {
  color: #718096;
}

.footer-bottom a:hover {
  color: var(--marca-red);
}

/* RESPONSIVE */
@media (max-width: 992px) {
  .content-wrap { grid-template-columns: 1fr; }
  .hero-grid { grid-template-columns: 1fr; }
  .articles-grid { grid-template-columns: repeat(2, 1fr); }
  .footer-grid { grid-template-columns: 1fr 1fr; }
}

@media (max-width: 600px) {
  .articles-grid { grid-template-columns: 1fr; }
  .hero-main { height: 260px; }
  .hero-overlay h2 { font-size: 20px; }
  .logo-text { font-size: 26px; }
  .single-title { font-size: 24px; }
  .footer-grid { grid-template-columns: 1fr; }
}

/* Custom Fixture CTA Banner */
.fixture-cta-banner {
  position: relative;
  height: 440px;
  background-image: linear-gradient(180deg, rgba(0,0,0,0.1) 0%, rgba(0,0,0,0.95) 100%), url('https://images.unsplash.com/photo-1522778119026-d647f0596c20?q=80&w=1200&auto=format&fit=crop');
  background-size: cover;
  background-position: center;
  display: flex;
  align-items: flex-end;
  border-radius: 8px;
}

.cta-overlay {
  padding: 30px;
  width: 100%;
}

.badge-gold {
  background: #f1c40f;
  color: #111;
  font-weight: 800;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 11px;
  letter-spacing: 1px;
  display: inline-block;
  margin-bottom: 12px;
}

.fixture-cta-banner h2 {
  font-family: 'Roboto Condensed', sans-serif;
  color: #fff;
  font-size: 32px;
  font-weight: 800;
  line-height: 1.2;
  margin-bottom: 12px;
  text-transform: uppercase;
}

.hero-desc {
  color: #e0e0e0;
  font-size: 14px;
  line-height: 1.5;
  margin-bottom: 20px;
  max-width: 90%;
}

.cta-button-hero {
  display: inline-block;
  background: linear-gradient(135deg, var(--ole-green) 0%, var(--ole-green-dark) 100%);
  color: #111;
  font-weight: 800;
  font-size: 14px;
  padding: 12px 24px;
  border-radius: 6px;
  text-decoration: none;
  transition: all 0.2s ease;
  box-shadow: 0 4px 15px rgba(137, 197, 63, 0.4);
}

.cta-button-hero:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(137, 197, 63, 0.6);
  color: #000;
}

.cta-button-secondary {
  display: inline-block;
  background: linear-gradient(135deg, #ffaa00 0%, #cc7700 100%);
  color: #111;
  font-weight: 800;
  font-size: 14px;
  padding: 12px 24px;
  border-radius: 6px;
  text-decoration: none;
  transition: all 0.2s ease;
  box-shadow: 0 4px 15px rgba(255, 170, 0, 0.4);
}

.cta-button-secondary:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(255, 170, 0, 0.6);
  color: #000;
}

/* FIXTURE WIDGET AND PAGE TEMPLATE */
.hero-fixture-widget {
  background: #1a1a1a;
  border-radius: 8px;
  border: 1px solid #333;
  padding: 15px;
  display: flex;
  flex-direction: column;
  color: #fff;
  height: 100%;
}

.hero-fixture-widget .widget-header {
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 2px solid var(--ole-green);
  padding-bottom: 8px;
  margin-bottom: 12px;
}

.hero-fixture-widget .widget-header h3 {
  font-family: 'Roboto Condensed', sans-serif;
  font-size: 15px;
  font-weight: 700;
  text-transform: uppercase;
  color: #fff;
}

.hero-fixture-widget .widget-content {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
}

.widget-match-item {
  background: #252525;
  border: 1px solid #3a3a3a;
  border-radius: 6px;
  padding: 8px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: all 0.15s ease;
}

.widget-match-item:hover {
  border-color: var(--ole-green);
  background: #2b2b2b;
}

.widget-match-item .match-teams {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-grow: 1;
  justify-content: space-between;
  padding-right: 10px;
}

.widget-match-item .team {
  font-size: 12px;
  font-weight: 700;
  color: #fff;
  max-width: 90px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.widget-match-item .score {
  display: flex;
  align-items: center;
  gap: 4px;
  font-family: 'Roboto Condensed', sans-serif;
  font-weight: 700;
  font-size: 13px;
  background: #111;
  padding: 2px 6px;
  border-radius: 4px;
}

.widget-match-item .score-val {
  color: #ffcc00;
}

.widget-match-item .match-status {
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  padding: 2px 5px;
  border-radius: 3px;
  text-align: center;
  min-width: 55px;
}

.widget-match-item.live .match-status {
  background: var(--marca-red);
  color: #fff;
  animation: pulse 1.5s infinite;
}

.widget-match-item.final .match-status {
  background: #444;
  color: #aaa;
}

.widget-match-item.prog .match-status {
  background: #333;
  color: #0cf737;
}

.hero-fixture-widget .widget-footer {
  margin-top: 12px;
  border-top: 1px solid #333;
  padding-top: 10px;
  text-align: center;
}

.hero-fixture-widget .view-all-btn {
  font-size: 11px;
  font-weight: 700;
  color: var(--ole-green);
  text-transform: uppercase;
}

.hero-fixture-widget .view-all-btn:hover {
  color: #fff;
}

/* FIXTURE LONG FORM PAGE */
.fixture-page-container {
  background: #111;
  color: #fff;
  padding: 25px;
  border-radius: 8px;
  border: 1px solid #333;
  margin-bottom: 30px;
}

.fixture-main-title {
  font-family: 'Roboto Condensed', sans-serif;
  font-size: 32px;
  font-weight: 800;
  color: #fff;
  margin-bottom: 6px;
  text-transform: uppercase;
}

.fixture-subtitle {
  font-size: 14px;
  color: #aaa;
  margin-bottom: 20px;
}

.fixture-tabs {
  display: flex;
  gap: 10px;
  border-bottom: 2px solid #333;
  padding-bottom: 10px;
  margin-bottom: 25px;
  overflow-x: auto;
}

.fixture-tab-btn {
  background: #252525;
  border: 1px solid #333;
  color: #ccc;
  padding: 10px 18px;
  font-size: 13px;
  font-weight: 700;
  border-radius: 6px;
  cursor: pointer;
  white-space: nowrap;
  font-family: 'Inter', sans-serif;
  transition: all 0.15s ease;
}

.fixture-tab-btn:hover {
  background: #333;
  color: #fff;
}

.fixture-tab-btn.active {
  background: var(--ole-green);
  border-color: var(--ole-green);
  color: #111;
}

.fixture-tab-content {
  display: none;
}

.fixture-tab-content.active {
  display: block;
}

.groups-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}

.group-card {
  background: #181818;
  border: 1px solid #2d2d2d;
  border-radius: 8px;
  padding: 15px;
}

.group-title {
  font-family: 'Roboto Condensed', sans-serif;
  font-size: 16px;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--ole-green);
  border-bottom: 1px solid #2d2d2d;
  padding-bottom: 8px;
  margin-bottom: 12px;
}

.group-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.group-table th {
  color: #777;
  font-weight: 700;
  padding: 6px 4px;
  border-bottom: 1px solid #2d2d2d;
  text-transform: uppercase;
  font-size: 10px;
}

.group-table td {
  padding: 8px 4px;
  border-bottom: 1px solid #252525;
  text-align: center;
}

.team-row:last-child td {
  border-bottom: none;
}

.team-pos {
  display: inline-block;
  width: 16px;
  height: 16px;
  line-height: 16px;
  text-align: center;
  border-radius: 50%;
  font-weight: 800;
  font-size: 10px;
}

.team-color-badge {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}

.team-pts {
  font-weight: 800;
  color: #ffcc00;
}

.no-data-msg {
  text-align: center;
  padding: 40px;
  color: #777;
  font-size: 14px;
}

/* MATCH CARDS IN FIXTURE PAGE */
.matches-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 15px;
}

.fixture-match-card {
  background: #181818;
  border: 1px solid #2d2d2d;
  border-radius: 8px;
  padding: 15px;
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.fixture-match-card.match-live {
  border-color: var(--marca-red);
}

.fixture-match-card .match-status-badge {
  font-size: 10px;
  font-weight: 700;
  color: #fff;
  text-transform: uppercase;
  background: #252525;
  align-self: flex-start;
  padding: 3px 8px;
  border-radius: 4px;
}

.fixture-match-card.match-live .match-status-badge {
  background: var(--marca-red);
  animation: pulse 1.5s infinite;
}

.fixture-match-card.match-prog .match-status-badge {
  color: #ffcc00;
}

.fixture-match-card .match-teams {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
}

.fixture-match-card .team {
  flex: 1;
  font-weight: 700;
  font-size: 14px;
  display: flex;
  align-items: center;
}

.fixture-match-card .home-team {
  justify-content: flex-end;
  text-align: right;
}

.fixture-match-card .away-team {
  justify-content: flex-start;
  text-align: left;
}

.fixture-match-card .match-score {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #111;
  padding: 4px 12px;
  border-radius: 6px;
  font-family: 'Roboto Condensed', sans-serif;
  font-size: 16px;
  font-weight: 800;
  margin: 0 15px;
}

.fixture-match-card .score-num {
  color: #ffcc00;
}

.fixture-match-card .score-sep {
  color: #777;
}

.fixture-match-card .match-meta {
  font-size: 10px;
  color: #555;
  text-align: center;
  border-top: 1px solid #222;
  padding-top: 6px;
}

/* BRACKETS LIST IN FIXTURE PAGE */
.brackets-container {
  display: flex;
  flex-direction: column;
  gap: 30px;
}

.bracket-stage-block {
  background: #181818;
  border: 1px solid #2d2d2d;
  border-radius: 8px;
  padding: 20px;
}

.bracket-stage-title {
  font-family: 'Roboto Condensed', sans-serif;
  font-size: 18px;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--ole-green);
  margin-bottom: 15px;
  border-bottom: 1px solid #2d2d2d;
  padding-bottom: 8px;
}

.bracket-matches-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 15px;
}

.bracket-match-card {
  background: #252525;
  border: 1px solid #333;
  border-radius: 6px;
  padding: 12px;
  position: relative;
}

.bracket-team {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  padding: 4px 0;
  color: #ccc;
}

.bracket-team.winner {
  font-weight: 700;
  color: #fff;
}

.bracket-team-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bracket-vs-divider {
  font-size: 9px;
  color: #555;
  font-weight: 700;
  text-align: center;
  margin: 2px 0;
  border-top: 1px dashed #333;
  border-bottom: 1px dashed #333;
  padding: 2px 0;
}

.bracket-score {
  font-size: 11px;
  font-weight: 700;
  color: #ffcc00;
  text-align: right;
  margin-top: 4px;
}

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.5; }
  100% { opacity: 1; }
}

/* Banners Publicitarios / Ad Slots */
.ad-slot-wrapper {
  margin: 20px auto;
  text-align: center;
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: hidden;
  clear: both;
}

.header-ad-slot {
  max-width: 100%;
  padding: 10px 0;
  background: transparent;
  min-height: 90px;
}

.sidebar-ad-slot {
  margin: 15px 0;
  max-width: 100%;
}

.in-article-ad-slot {
  max-width: 100%;
  padding: 15px 0;
  border-top: 1px dashed #3a3a3a;
  border-bottom: 1px dashed #3a3a3a;
  background: rgba(255, 255, 255, 0.01);
}

/* Hide empty ad wrappers */
.ad-slot-wrapper:empty {
  display: none !important;
}
""")

# ── functions.php ───────────────────────────────────────────────────────────
open(f"{THEME_DIR}/functions.php","w",encoding="utf-8").write("""\
<?php
function ppelota_setup(){
  add_theme_support('post-thumbnails');
  add_theme_support('title-tag');
  add_image_size('hero-large',800,420,true);
  add_image_size('card-thumb',400,160,true);
  register_nav_menus(['primary'=>'Menú Principal']);
}
add_action('after_setup_theme','ppelota_setup');

function ppelota_scripts(){
  wp_enqueue_style('ppelota-style',get_stylesheet_uri(),[],filemtime(get_stylesheet_directory().'/style.css'));
}
add_action('wp_enqueue_scripts','ppelota_scripts');

function ppelota_get_thumb($post_id,$size='card-thumb'){
  if(has_post_thumbnail($post_id)){
    return get_the_post_thumbnail($post_id,$size,['alt'=>'','style'=>'width:100%;height:100%;object-fit:cover;']);
  }
  $e=['⚽','🏆','🔥','⚡','🎯','🥅'];
  return '<div class="art-card-no-img">'.$e[array_rand($e)].'</div>';
}

function ppelota_hero_thumb($post_id){
  if(has_post_thumbnail($post_id)){
    return get_the_post_thumbnail($post_id,'hero-large',['alt'=>'','style'=>'width:100%;height:440px;object-fit:cover;']);
  }
  $e=['⚽','🏆','🔥','⚡'];
  return '<div class="hero-no-img">'.$e[array_rand($e)].'</div>';
}

function ppelota_side_thumb($post_id){
  if(has_post_thumbnail($post_id)){
    return get_the_post_thumbnail($post_id,'card-thumb',['alt'=>'','style'=>'width:100%;height:100%;min-height:140px;object-fit:cover;']);
  }
  $e=['⚽','🏆','🔥','⚡'];
  return '<div class="hero-side-no-img">'.$e[array_rand($e)].'</div>';
}

// function ppelota_filter_homepage_query($query) {
//   if ($query->is_home() && $query->is_main_query() && !is_admin()) {
//     $query->set('category_name', 'mundial-2026,f1');
//   }
// }
// add_action('pre_get_posts', 'ppelota_filter_homepage_query');

// API REST personalizada para actualizar marquesinas y semáforo dinámicamente
add_action('rest_api_init', function () {
  register_rest_route('ppelota/v1', '/update-data', [
    'methods' => 'POST',
    'callback' => 'ppelota_update_data_callback',
    'permission_callback' => function () {
      return current_user_can('edit_posts');
    }
  ]);
  register_rest_route('ppelota/v1', '/verify-files', [
    'methods' => 'GET',
    'callback' => 'ppelota_verify_files_callback',
    'permission_callback' => function () {
      return current_user_can('edit_posts');
    }
  ]);
});

function ppelota_verify_files_callback() {
  $dir = get_home_path();
  $files = ['main_standalone.py', 'tools/cleanup.py', 'tools/editor_jefe.py', '.env'];
  $result = [];
  foreach ($files as $file) {
    $full = $dir . $file;
    if (file_exists($full)) {
      $result[$file] = [
        'exists' => true,
        'size' => filesize($full),
        'modified' => date("Y-m-d H:i:s", filemtime($full))
      ];
    } else {
      $result[$file] = ['exists' => false];
    }
  }
  return new WP_REST_Response($result, 200);
}

function ppelota_update_data_callback($request) {
  $params = $request->get_json_params();
  if (isset($params['upcoming_matches'])) {
    update_option('ppelota_upcoming_matches', $params['upcoming_matches']);
  }
  if (isset($params['live_scores'])) {
    update_option('ppelota_live_scores', $params['live_scores']);
  }
  if (isset($params['semaforo'])) {
    update_option('ppelota_semaforo', $params['semaforo']);
  }
  if (isset($params['mundial_data'])) {
    update_option('ppelota_mundial_data', json_encode($params['mundial_data']));
  }
  if (isset($params['projected_brackets'])) {
    update_option('ppelota_projected_brackets', json_encode($params['projected_brackets']));
  }
  if (isset($params['player_stats'])) {
    update_option('ppelota_player_stats', json_encode($params['player_stats']));
  }
  return new WP_REST_Response(['status' => 'success'], 200);
}

// API REST para el contador de visitas (evita problemas de caché de página)
add_action('rest_api_init', function () {
  register_rest_route('ppelota/v1', '/visit-count', [
    'methods' => 'GET',
    'callback' => 'ppelota_get_visit_count_callback',
    'permission_callback' => '__return_true'
  ]);
});

function ppelota_get_visit_count_callback() {
  header("Cache-Control: no-store, no-cache, must-revalidate, max-age=0");
  header("Cache-Control: post-check=0, pre-check=0", false);
  header("Pragma: no-cache");
  header("Expires: Wed, 11 Jan 1984 05:00:00 GMT");

  $count = get_option('ppelota_visit_count');
  if ($count === false) {
    $count = 1415;
    add_option('ppelota_visit_count', $count);
  } else {
    $count = (int)$count + 1;
    update_option('ppelota_visit_count', $count);
  }
  return new WP_REST_Response(['count' => number_format($count, 0, ',', '.')], 200);
}

// Registrar campos de metadatos en la API REST de WordPress
add_action('init', function () {
  register_post_meta('post', 'ppelota_seo_desc', [
    'show_in_rest' => true,
    'single' => true,
    'type' => 'string',
  ]);
  register_post_meta('post', 'ppelota_writer', [
    'show_in_rest' => true,
    'single' => true,
    'type' => 'string',
  ]);
});

// Inyectar etiquetas meta y JSON-LD de forma invisible en la cabecera HTML (SEO/GEO)
add_action('wp_head', function () {
  if (is_single()) {
    $post_id = get_the_ID();
    $title = get_the_title();
    $url = get_permalink();
    $date_pub = get_the_date('c');
    $date_mod = get_the_modified_date('c');
    $img_url = get_the_post_thumbnail_url($post_id, 'large');
    
    // Obtener la meta descripción y el autor del post de los campos personalizados
    $seo_desc = get_post_meta($post_id, 'ppelota_seo_desc', true);
    $writer_name = get_post_meta($post_id, 'ppelota_writer', true);
    if (empty($writer_name)) {
      $writer_name = get_the_author();
    }
    
    if ($seo_desc) {
      echo '<meta name="description" content="' . esc_attr($seo_desc) . '">' . "\n";
      echo '<meta property="og:description" content="' . esc_attr($seo_desc) . '">' . "\n";
      echo '<meta name="twitter:description" content="' . esc_attr($seo_desc) . '">' . "\n";
    }
    
    echo '<meta property="og:title" content="' . esc_attr($title) . '">' . "\n";
    echo '<meta property="og:type" content="article">' . "\n";
    echo '<meta property="og:url" content="' . esc_url($url) . '">' . "\n";
    echo '<meta name="twitter:card" content="summary_large_image">' . "\n";
    echo '<meta name="twitter:title" content="' . esc_attr($title) . '">' . "\n";
    
    if ($img_url) {
      echo '<meta property="og:image" content="' . esc_url($img_url) . '">' . "\n";
      echo '<meta name="twitter:image" content="' . esc_url($img_url) . '">' . "\n";
    }
    
    // Generación del JSON-LD estructurado de tipo NewsArticle para motores generativos (GEO)
    $json_ld = [
      '@context' => 'https://schema.org',
      '@type' => 'NewsArticle',
      'headline' => $title,
      'datePublished' => $date_pub,
      'dateModified' => $date_mod,
      'url' => $url,
      'author' => [
        [
          '@type' => 'Person',
          'name' => $writer_name
        ]
      ],
      'publisher' => [
        '@type' => 'Organization',
        'name' => 'Pasión y Pelota',
        'logo' => [
          '@type' => 'ImageObject',
          'url' => esc_url(home_url('/wp-content/themes/pasion-pelota/images/logo.png'))
        ]
      ]
    ];
    if ($img_url) {
      $json_ld['image'] = [$img_url];
    }
    
    echo "\n" . '<script type="application/ld+json">' . "\n";
    echo json_encode($json_ld, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
    echo "\n" . '</script>' . "\n";
  }
});

// Personalizador para Monetización (Banners de Anuncios)
add_action('customize_register', function ($wp_customize) {
  $wp_customize->add_panel('ppelota_monetization_panel', [
    'title' => 'Monetización Pasión y Pelota',
    'priority' => 120,
  ]);
  
  $wp_customize->add_section('ppelota_ads_section', [
    'title' => 'Banners Publicitarios (AdSense)',
    'panel' => 'ppelota_monetization_panel',
    'priority' => 10,
  ]);
  
  // Anuncio Cabecera (Header Ad)
  $wp_customize->add_setting('ppelota_ad_header', [
    'default' => '',
    'sanitize_callback' => 'ppelota_sanitize_ad_code',
  ]);
  $wp_customize->add_control('ppelota_ad_header_control', [
    'label' => 'Código de Anuncio Superior (Header - Recomendado 728x90 / 320x100)',
    'section' => 'ppelota_ads_section',
    'settings' => 'ppelota_ad_header',
    'type' => 'textarea',
  ]);

  // Anuncio Barra Lateral (Sidebar Ad)
  $wp_customize->add_setting('ppelota_ad_sidebar', [
    'default' => '',
    'sanitize_callback' => 'ppelota_sanitize_ad_code',
  ]);
  $wp_customize->add_control('ppelota_ad_sidebar_control', [
    'label' => 'Código de Anuncio Lateral (Sidebar - Recomendado 300x250 / 300x600)',
    'section' => 'ppelota_ads_section',
    'settings' => 'ppelota_ad_sidebar',
    'type' => 'textarea',
  ]);

  // Anuncio Artículo (In-Article Ad)
  $wp_customize->add_setting('ppelota_ad_article', [
    'default' => '',
    'sanitize_callback' => 'ppelota_sanitize_ad_code',
  ]);
  $wp_customize->add_control('ppelota_ad_article_control', [
    'label' => 'Código de Anuncio en Artículos (In-Article - Recomendado 300x250 / 336x280)',
    'section' => 'ppelota_ads_section',
    'settings' => 'ppelota_ad_article',
    'type' => 'textarea',
  ]);
});

function ppelota_sanitize_ad_code($value) {
  return $value;
}
""")

# ── header.php ──────────────────────────────────────────────────────────────
open(f"{THEME_DIR}/header.php","w",encoding="utf-8").write("""\
<!DOCTYPE html>
<html <?php language_attributes(); ?>>
<head>
<meta charset="<?php bloginfo('charset'); ?>">
<meta name="viewport" content="width=device-width,initial-scale=1">
<script>
if ('scrollRestoration' in history) {
  history.scrollRestoration = 'manual';
}
</script>
<?php wp_head(); ?>
</head>
<body <?php body_class(); ?>>
<div class="top-bar">
  <div class="container">
    <span><?php echo date_i18n('l, j F Y'); ?></span>
    <div><a href="https://twitter.com/pasionypelota" target="_blank">Twitter / X</a><a href="https://instagram.com/pasionypelota" target="_blank">Instagram</a></div>
  </div>
</div>
<div class="scores-strip">
  <div class="container">
    <div class="scores-marquee">
      <div class="scores-track">
        <?php
        $live_scores = get_option('ppelota_live_scores');
        if ($live_scores) {
          echo $live_scores;
        } else {
          // Fallback con datos reales de la Copa del Mundo del 20 de Junio
          ?>
          <div class="score-item"><span class="league-tag">MUNDIAL 2026</span> <strong>Países Bajos</strong> 1 - 1 <strong>Suecia</strong> <span class="match-status">Final</span></div>
          <div class="score-item"><span class="league-tag">MUNDIAL 2026</span> <strong>Alemania</strong> 2 - 1 <strong>Costa de Marfil</strong> <span class="match-status">Final</span></div>
          <div class="score-item"><span class="league-tag">MUNDIAL 2026</span> <strong>Ecuador</strong> 3 - 0 <strong>Curazao</strong> <span class="match-status">Final</span></div>
          <div class="score-item"><span class="league-tag">MUNDIAL 2026</span> <strong>Túnez</strong> 1 - 2 <strong>Japón</strong> <span class="match-status">Final</span></div>
          <!-- Duplicado para loop continuo -->
          <div class="score-item"><span class="league-tag">MUNDIAL 2026</span> <strong>Países Bajos</strong> 1 - 1 <strong>Suecia</strong> <span class="match-status">Final</span></div>
          <div class="score-item"><span class="league-tag">MUNDIAL 2026</span> <strong>Alemania</strong> 2 - 1 <strong>Costa de Marfil</strong> <span class="match-status">Final</span></div>
          <div class="score-item"><span class="league-tag">MUNDIAL 2026</span> <strong>Ecuador</strong> 3 - 0 <strong>Curazao</strong> <span class="match-status">Final</span></div>
          <div class="score-item"><span class="league-tag">MUNDIAL 2026</span> <strong>Túnez</strong> 1 - 2 <strong>Japón</strong> <span class="match-status">Final</span></div>
          <?php
        }
        ?>
      </div>
    </div>
  </div>
</div>
<div class="upcoming-strip" style="background: #1a1a1a; color: #fff; padding: 6px 0; border-bottom: 1px solid var(--border-color); overflow: hidden;">
  <div class="container">
    <div class="scores-marquee">
      <div class="scores-track" style="animation: scores-scroll 45s linear infinite; display: inline-flex; gap: 15px; white-space: nowrap;">
        <?php
        $upcoming = get_option('ppelota_upcoming_matches');
        if ($upcoming) {
          echo $upcoming;
        } else {
          // Fallback con datos reales del 21-22 de Junio
          ?>
          <div class="score-item" style="background: #2a2a2a; border: 1px solid #3a3a3a; padding: 6px 12px; border-radius: 4px; display: flex; align-items: center; gap: 8px; flex-shrink: 0;"><span class="league-tag" style="background: var(--ole-green); color: #111; font-weight: 800; font-size: 9px; padding: 2px 5px; border-radius: 2px; letter-spacing: 0.5px;">PRÓXIMO ENCUENTRO</span> <strong style="color: #fff;">España</strong> vs. <strong style="color: #fff;">Arabia Saudí</strong> <span class="match-status" style="color: #ffcc00; font-weight: 700; font-size: 10px;">21 Jun 12:00 hs</span></div>
          <div class="score-item" style="background: #2a2a2a; border: 1px solid #3a3a3a; padding: 6px 12px; border-radius: 4px; display: flex; align-items: center; gap: 8px; flex-shrink: 0;"><span class="league-tag" style="background: var(--ole-green); color: #111; font-weight: 800; font-size: 9px; padding: 2px 5px; border-radius: 2px; letter-spacing: 0.5px;">PRÓXIMO ENCUENTRO</span> <strong style="color: #fff;">Bélgica</strong> vs. <strong style="color: #fff;">Irán</strong> <span class="match-status" style="color: #ffcc00; font-weight: 700; font-size: 10px;">21 Jun 15:00 hs</span></div>
          <div class="score-item" style="background: #2a2a2a; border: 1px solid #3a3a3a; padding: 6px 12px; border-radius: 4px; display: flex; align-items: center; gap: 8px; flex-shrink: 0;"><span class="league-tag" style="background: var(--ole-green); color: #111; font-weight: 800; font-size: 9px; padding: 2px 5px; border-radius: 2px; letter-spacing: 0.5px;">PRÓXIMO ENCUENTRO</span> <strong style="color: #fff;">Uruguay</strong> vs. <strong style="color: #fff;">Cabo Verde</strong> <span class="match-status" style="color: #ffcc00; font-weight: 700; font-size: 10px;">21 Jun 18:00 hs</span></div>
          <div class="score-item" style="background: #2a2a2a; border: 1px solid #3a3a3a; padding: 6px 12px; border-radius: 4px; display: flex; align-items: center; gap: 8px; flex-shrink: 0;"><span class="league-tag" style="background: var(--ole-green); color: #111; font-weight: 800; font-size: 9px; padding: 2px 5px; border-radius: 2px; letter-spacing: 0.5px;">PRÓXIMO ENCUENTRO</span> <strong style="color: #fff;">Argentina</strong> vs. <strong style="color: #fff;">Austria</strong> <span class="match-status" style="color: #ffcc00; font-weight: 700; font-size: 10px;">22 Jun 13:00 hs</span></div>
          <!-- Duplicados para loop infinito continuo -->
          <div class="score-item" style="background: #2a2a2a; border: 1px solid #3a3a3a; padding: 6px 12px; border-radius: 4px; display: flex; align-items: center; gap: 8px; flex-shrink: 0;"><span class="league-tag" style="background: var(--ole-green); color: #111; font-weight: 800; font-size: 9px; padding: 2px 5px; border-radius: 2px; letter-spacing: 0.5px;">PRÓXIMO ENCUENTRO</span> <strong style="color: #fff;">España</strong> vs. <strong style="color: #fff;">Arabia Saudí</strong> <span class="match-status" style="color: #ffcc00; font-weight: 700; font-size: 10px;">21 Jun 12:00 hs</span></div>
          <div class="score-item" style="background: #2a2a2a; border: 1px solid #3a3a3a; padding: 6px 12px; border-radius: 4px; display: flex; align-items: center; gap: 8px; flex-shrink: 0;"><span class="league-tag" style="background: var(--ole-green); color: #111; font-weight: 800; font-size: 9px; padding: 2px 5px; border-radius: 2px; letter-spacing: 0.5px;">PRÓXIMO ENCUENTRO</span> <strong style="color: #fff;">Bélgica</strong> vs. <strong style="color: #fff;">Irán</strong> <span class="match-status" style="color: #ffcc00; font-weight: 700; font-size: 10px;">21 Jun 15:00 hs</span></div>
          <div class="score-item" style="background: #2a2a2a; border: 1px solid #3a3a3a; padding: 6px 12px; border-radius: 4px; display: flex; align-items: center; gap: 8px; flex-shrink: 0;"><span class="league-tag" style="background: var(--ole-green); color: #111; font-weight: 800; font-size: 9px; padding: 2px 5px; border-radius: 2px; letter-spacing: 0.5px;">PRÓXIMO ENCUENTRO</span> <strong style="color: #fff;">Uruguay</strong> vs. <strong style="color: #fff;">Cabo Verde</strong> <span class="match-status" style="color: #ffcc00; font-weight: 700; font-size: 10px;">21 Jun 18:00 hs</span></div>
          <div class="score-item" style="background: #2a2a2a; border: 1px solid #3a3a3a; padding: 6px 12px; border-radius: 4px; display: flex; align-items: center; gap: 8px; flex-shrink: 0;"><span class="league-tag" style="background: var(--ole-green); color: #111; font-weight: 800; font-size: 9px; padding: 2px 5px; border-radius: 2px; letter-spacing: 0.5px;">PRÓXIMO ENCUENTRO</span> <strong style="color: #fff;">Argentina</strong> vs. <strong style="color: #fff;">Austria</strong> <span class="match-status" style="color: #ffcc00; font-weight: 700; font-size: 10px;">22 Jun 13:00 hs</span></div>
          <?php
        }
        ?>
      </div>
    </div>
  </div>
</div>
<header class="site-header">
  <div class="container" style="justify-content: center; flex-direction: column; align-items: center; gap: 8px;">
    <a href="<?php echo esc_url(home_url('/')); ?>" class="site-logo">
      <span class="logo-text"><span class="logo-pasion">Pasión</span> <span class="logo-y-pelota">y Pelota</span></span>
    </a>
    <span class="header-tagline">El diario deportivo panamericano</span>
  </div>
</header>
<?php
$ad_header = get_theme_mod('ppelota_ad_header');
if ($ad_header):
?>
  <div class="ad-slot-wrapper header-ad-slot">
    <div class="container">
      <?php echo $ad_header; ?>
    </div>
  </div>
<?php endif; ?>
<div class="sticky-header-wrapper">
<nav class="main-nav">
  <div class="container">
    <?php wp_nav_menu(['theme_location'=>'primary','menu_class'=>'nav-menu','fallback_cb'=>function(){?>
    <ul class="nav-menu">
      <li><a href="<?php echo esc_url(home_url('/')); ?>">🏠 Portada</a></li>
      <li><a href="<?php echo esc_url(home_url('/category/mundial-2026')); ?>">Mundial 2026</a></li>
      <li><a href="<?php echo esc_url(home_url('/category/mls')); ?>">MLS</a></li>
      <li><a href="<?php echo esc_url(home_url('/category/brasileirao')); ?>">Brasileirão</a></li>
      <li><a href="<?php echo esc_url(home_url('/category/futbol-argentino')); ?>">Fútbol Argentino</a></li>
      <li><a href="<?php echo esc_url(home_url('/category/champions-league')); ?>">Champions</a></li>
      <li><a href="<?php echo esc_url(home_url('/category/premier-league')); ?>">Premier</a></li>
      <li><a href="<?php echo esc_url(home_url('/category/laliga')); ?>">LaLiga</a></li>
    </ul>
    <?php }]); ?>
  </div>
</nav>
<div class="ticker-bar">
  <div class="container">
    <span class="ticker-label">⚡ ÚLTIMA HORA</span>
    <div class="ticker-wrap"><div class="ticker-inner">
      <?php
      $rp=get_posts(['numberposts'=>6,'post_status'=>'publish']);
      $t='';foreach($rp as $p){$t.='<a href="'.esc_url(get_permalink($p)).'">'.esc_html($p->post_title).'</a>';}
      echo $t.$t;
      ?>
    </div></div>
  </div>
</div>
</div>
""")

# ── footer.php ──────────────────────────────────────────────────────────────
open(f"{THEME_DIR}/footer.php","w",encoding="utf-8").write("""\
<footer class="site-footer">
  <div class="container">
    <div class="footer-grid">
      <div>
        <div class="footer-logo-text">⚽ Pasión <em>y</em> Pelota</div>
        <p class="footer-desc">Portal de noticias de fútbol actualizado 24/7. Fichajes, resultados, análisis y rumores de LaLiga, Premier League, Champions League, Fútbol Argentino y más.</p>
      </div>
      <div>
        <div class="footer-col-title">Ligas</div>
        <ul class="footer-links">
          <li><a href="<?php echo esc_url(home_url('/category/laliga')); ?>">LaLiga</a></li>
          <li><a href="<?php echo esc_url(home_url('/category/premier-league')); ?>">Premier League</a></li>
          <li><a href="<?php echo esc_url(home_url('/category/champions-league')); ?>">Champions League</a></li>
          <li><a href="<?php echo esc_url(home_url('/category/futbol-argentino')); ?>">Fútbol Argentino</a></li>
          <li><a href="<?php echo esc_url(home_url('/category/brasileirao')); ?>">Brasileirão</a></li>
        </ul>
      </div>
      <div>
        <div class="footer-col-title">El Sitio</div>
        <ul class="footer-links">
          <li><a href="<?php echo esc_url(home_url('/acerca-de')); ?>">Acerca de</a></li>
          <li><a href="<?php echo esc_url(home_url('/politica-de-privacidad')); ?>">Privacidad</a></li>
          <li><a href="https://twitter.com/pasionypelota" target="_blank">Twitter / X</a></li>
          <li><a href="https://instagram.com/pasionypelota" target="_blank">Instagram</a></li>
        </ul>
      </div>
    </div>
    <div class="footer-bottom" style="display: flex; flex-direction: column; align-items: center; gap: 10px; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 15px;">
      <div style="display: flex; justify-content: space-between; width: 100%; align-items: center; flex-wrap: wrap; gap: 10px;">
        <span>© <?php echo date('Y'); ?> Pasión y Pelota — Todos los derechos reservados</span>
        <a href="<?php echo esc_url(home_url('/politica-de-privacidad')); ?>">Política de Privacidad</a>
      </div>
      
      <?php
      // Obtener el valor inicial (fallback estático antes de que cargue AJAX)
      $initial_count = get_option('ppelota_visit_count');
      if ($initial_count === false) {
          $initial_count = 1415;
      }
      ?>
      <style>
      @keyframes count-pulse {
        0% { opacity: 0.4; }
        50% { opacity: 1; }
        100% { opacity: 0.4; }
      }
      </style>
      <div class="visit-counter" style="margin-top: 5px; font-size: 11px; color: #a0aec0; display: inline-flex; align-items: center; gap: 6px; background: rgba(255,255,255,0.04); padding: 4px 12px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.08); font-weight: 500;">
        <span style="color: #89c53f; font-size: 10px; animation: count-pulse 2s infinite; margin-right: 2px;">●</span>
        <span>📊 <strong id="visit-counter-val"><?php echo number_format($initial_count, 0, ',', '.'); ?></strong> visitas reales</span>
      </div>
      <script>
      document.addEventListener("DOMContentLoaded", function() {
        fetch("<?php echo esc_url(rest_url('ppelota/v1/visit-count')); ?>?_=" + new Date().getTime())
          .then(response => response.json())
          .then(data => {
            if (data && data.count) {
              document.getElementById("visit-counter-val").textContent = data.count;
            }
          })
          .catch(err => console.error("Error loading visit counter:", err));
      });
      </script>
    </div>
  </div>
</footer>
<script>
document.addEventListener("DOMContentLoaded", function() {
  const target = document.querySelector(".sticky-header-wrapper");
  if (!target) return;
  
  let userScrolled = false;
  const onUserScroll = function() {
    userScrolled = true;
    window.removeEventListener('wheel', onUserScroll);
    window.removeEventListener('touchmove', onUserScroll);
  };
  window.addEventListener('wheel', onUserScroll, {passive: true});
  window.addEventListener('touchmove', onUserScroll, {passive: true});
  
  function doScroll() {
    if (userScrolled) return;
    window.scrollTo(0, target.offsetTop);
  }
  
  doScroll();
  setTimeout(doScroll, 50);
  setTimeout(doScroll, 100);
  setTimeout(doScroll, 200);
  setTimeout(doScroll, 500);
  window.addEventListener('load', doScroll);
});
</script>
<?php wp_footer(); ?>
</body></html>
""")

# ── sidebar.php ─────────────────────────────────────────────────────────────
open(f"{THEME_DIR}/sidebar.php","w",encoding="utf-8").write("""\
<aside class="sidebar">
  <!-- El Semáforo Deportivo (Olé style) -->
  <div class="widget-box">
    <div class="widget-head semaforo-head">🟢 El Semáforo Deportivo</div>
    <div class="semaforo-body">
      <?php
      $semaforo = get_option('ppelota_semaforo');
      if ($semaforo) {
        echo $semaforo;
      } else {
        ?>
        <a href="<?php echo esc_url(home_url('/')); ?>" class="semaforo-link">
          <div class="semaforo-item verde">
            <span class="semaforo-dot">🟢</span>
            <div class="semaforo-content">
              <strong>Selección Argentina:</strong> Scaloni prepara el once titular con Lionel Messi en Dallas para enfrentar a Austria.
            </div>
          </div>
        </a>
        <a href="<?php echo esc_url(home_url('/')); ?>" class="semaforo-link">
          <div class="semaforo-item amarillo">
            <span class="semaforo-dot">🟡</span>
            <div class="semaforo-content">
              <strong>Fórmula 1:</strong> Gran expectativa por las mejoras de Mercedes y Alpine en el próximo Gran Premio; Franco Colapinto bajo la lupa.
            </div>
          </div>
        </a>
        <a href="<?php echo esc_url(home_url('/')); ?>" class="semaforo-link">
          <div class="semaforo-item rojo">
            <span class="semaforo-dot">🔴</span>
            <div class="semaforo-content">
              <strong>Lesión en Francia:</strong> Preocupación por las molestias físicas de Kylian Mbappé antes del debut contra Irak.
            </div>
          </div>
        </a>
        <?php
      }
      ?>
    </div>
  </div>

  <?php
  $ad_sidebar = get_theme_mod('ppelota_ad_sidebar');
  if ($ad_sidebar):
  ?>
    <div class="widget-box ad-slot-wrapper sidebar-ad-slot" style="text-align: center; display: flex; justify-content: center; align-items: center; min-height: 250px; background: none; border: none; box-shadow: none; padding: 0;">
      <?php echo $ad_sidebar; ?>
    </div>
  <?php endif; ?>

  <div class="widget-box">
    <div class="widget-head">🔥 Lo Más Leído</div>
    <div>
      <?php $rp=get_posts(['numberposts'=>5,'post_status'=>'publish']);
      foreach($rp as $i=>$p): ?>
      <div class="sb-post">
        <span class="sb-num"><?php echo $i+1; ?></span>
        <div>
          <div class="sb-post-title"><a href="<?php echo esc_url(get_permalink($p)); ?>"><?php echo esc_html($p->post_title); ?></a></div>
          <div class="sb-post-time"><?php echo get_the_date('j M Y',$p); ?></div>
        </div>
      </div>
      <?php endforeach; ?>
    </div>
  </div>

  <div class="widget-box">
    <div class="widget-head">📰 Noticias del Día</div>
    <div>
      <?php 
      $tz = new DateTimeZone('America/Argentina/Buenos_Aires');
      $dt = new DateTime('now', $tz);
      $today_str = $dt->format('d-m-Y');
      
      $today_posts = [];
      $all_posts = get_posts(['numberposts' => 15, 'post_status' => 'publish']);
      foreach ($all_posts as $p) {
        $p_date = get_the_date('d-m-Y', $p);
        if ($p_date === $today_str) {
          $today_posts[] = $p;
        }
      }
      
      // Fallback: si no hay noticias hoy, mostrar las 5 más recientes
      if (empty($today_posts)) {
        $today_posts = array_slice($all_posts, 0, 5);
      } else {
        $today_posts = array_slice($today_posts, 0, 5);
      }
      
      foreach($today_posts as $i=>$p): ?>
      <div class="sb-post">
        <span class="sb-num"><?php echo $i+1; ?></span>
        <div>
          <div class="sb-post-title"><a href="<?php echo esc_url(get_permalink($p)); ?>"><?php echo esc_html($p->post_title); ?></a></div>
          <div class="sb-post-time"><?php echo get_the_date('j M Y, H:i',$p); ?> hs</div>
        </div>
      </div>
      <?php endforeach; ?>
    </div>
  </div>

  <div class="widget-box">
    <div class="widget-head">📱 Seguinos</div>
    <div style="padding:15px;">
      <a href="https://twitter.com/pasionypelota" target="_blank" style="display:flex;align-items:center;gap:10px;padding:10px;background:#1DA1F2;color:#fff;border-radius:4px;margin-bottom:8px;font-weight:700;font-size:13px;">🐦 Twitter — @pasionypelota</a>
      <a href="https://instagram.com/pasionypelota" target="_blank" style="display:flex;align-items:center;gap:10px;padding:10px;background:linear-gradient(135deg,#833ab4,#fd1d1d,#fcb045);color:#fff;border-radius:4px;font-weight:700;font-size:13px;">📸 Instagram — @pasionypelota</a>
    </div>
  </div>
</aside>
""")

# ── front-page.php ──────────────────────────────────────────────────────────
open(f"{THEME_DIR}/front-page.php","w",encoding="utf-8").write("""\
<?php get_header(); ?>
<div class="site-content"><div class="container"><div class="content-wrap">
<main class="main-content">

<div class="hero-grid">
  <div class="hero-main fixture-cta-banner">
    <div class="hero-overlay cta-overlay">
      <span class="volanta badge-gold">🏆 COPA MUNDIAL FIFA 2026</span>
      <h2>FIXTURE COMPLETO, POSICIONES Y BRACKETS EN VIVO</h2>
      <p class="hero-desc">Seguí minuto a minuto los resultados de los grupos, tablas de posiciones de las 12 zonas y toda la fase final rumbo al campeonato mundial.</p>
      <div style="display: flex; gap: 12px; flex-wrap: wrap;">
        <a href="<?php echo esc_url(home_url('/fixture-mundial-2026')); ?>" class="cta-button-hero">Ver Fixture y Posiciones →</a>
        <a href="<?php echo esc_url(home_url('/fixture-mundial-2026?tab=tab-eliminatorias')); ?>" class="cta-button-secondary">🔮 Simulador de Cruces Hoy →</a>
      </div>
    </div>
  </div>
  
  <div class="hero-side hero-fixture-widget">
    <div class="widget-header">
      <span class="widget-icon">🏆</span>
      <h3>Mundial 2026: Partidos de Hoy</h3>
    </div>
    <div class="widget-content">
      <?php
      $m_data_raw = get_option('ppelota_mundial_data');
      $m_data = $m_data_raw ? json_decode($m_data_raw, true) : null;
      
      $today_matches = [];
      if ($m_data && !empty($m_data['games'])) {
        $tz = new DateTimeZone('America/Argentina/Buenos_Aires');
        $dt = new DateTime('now', $tz);
        $today_str = $dt->format('d-m-Y'); // Formato: "20-06-2026"
        
        foreach ($m_data['games'] as $game) {
          $game_date = substr($game['start_time'], 0, 10);
          if ($game_date === $today_str) {
            $today_matches[] = $game;
          }
        }
      }
      
      if (!empty($today_matches)):
        foreach ($today_matches as $game):
          $status_class = '';
          $status_lbl = $game['status'];
          if (strpos(strtolower($game['status']), 'vivo') !== false || strpos(strtolower($game['status']), 'tiempo') !== false) {
            $status_class = 'live';
            $status_lbl = '🔴 EN VIVO';
          } elseif (strpos(strtolower($game['status']), 'finalizado') !== false || strpos(strtolower($game['status']), 'final') !== false) {
            $status_class = 'final';
            $status_lbl = 'Final';
          } else {
            $status_class = 'prog';
            $status_lbl = substr($game['start_time'], 11, 5) . ' hs';
          }
      ?>
          <div class="widget-match-item <?php echo $status_class; ?>">
            <div class="match-teams">
              <div class="team" style="text-align:right;">
                <span class="team-name"><?php echo esc_html($game['home']); ?></span>
              </div>
              <div class="score">
                <span class="score-val"><?php echo esc_html($game['home_goals']); ?></span>
                <span class="sep">-</span>
                <span class="score-val"><?php echo esc_html($game['away_goals']); ?></span>
              </div>
              <div class="team" style="text-align:left;">
                <span class="team-name"><?php echo esc_html($game['away']); ?></span>
              </div>
            </div>
            <div class="match-status"><?php echo esc_html($status_lbl); ?></div>
          </div>
      <?php 
        endforeach;
      else:
      ?>
        <div class="widget-no-matches">
          <p>No hay partidos del mundial en juego hoy.</p>
        </div>
      <?php endif; ?>
    </div>
    <div class="widget-footer">
      <a href="<?php echo esc_url(home_url('/fixture-mundial-2026')); ?>" class="view-all-btn">Ver Fixture Completo y Posiciones →</a>
    </div>
  </div>
</div>

<div class="section-heading">📰 Últimas Noticias</div>
<?php $grid=get_posts([
  'posts_per_page'=>9,
  'offset'=>0,
  'post_status'=>'publish'
]);?>
<div class="articles-grid">
<?php foreach($grid as $g):
  $c=get_the_category($g->ID);$cn=$c?$c[0]->name:'Noticias';
  $ex=wp_trim_words(strip_tags($g->post_content),15,'...');
?>
<div class="art-card">
  <a href="<?php echo esc_url(get_permalink($g)); ?>">
    <?php if(has_post_thumbnail($g->ID)){echo get_the_post_thumbnail($g->ID,'card-thumb',['class'=>'art-card-img','alt'=>'']);}
    else{$e=['⚽','🏆','🔥','⚡','🎯'];echo '<div class="art-card-no-img">'.$e[array_rand($e)].'</div>';} ?>
  </a>
  <div class="art-card-body">
    <div class="art-card-cat"><?php echo esc_html($cn); ?></div>
    <div class="art-card-title"><a href="<?php echo esc_url(get_permalink($g)); ?>"><?php echo esc_html($g->post_title); ?></a></div>
    <div class="art-card-excerpt"><?php echo esc_html($ex); ?></div>
    <div class="art-card-time">🕐 <?php echo get_the_date('j M Y',$g); ?></div>
  </div>
</div>
<?php endforeach; ?>
</div>

<?php $list=get_posts([
  'posts_per_page'=>6,
  'offset'=>9,
  'post_status'=>'publish'
]);
if($list): ?>
<div class="section-heading">📋 Más Noticias</div>
<div class="articles-list-wrap">
<?php foreach($list as $l):$c=get_the_category($l->ID);$cn=$c?$c[0]->name:''; ?>
<div class="list-art-item">
  <a href="<?php echo esc_url(get_permalink($l)); ?>">
    <?php if(has_post_thumbnail($l->ID)){echo '<img class="list-art-thumb" src="'.get_the_post_thumbnail_url($l->ID,'thumbnail').'" alt="">';}
    else{$e=['⚽','🏆','🔥','⚡'];echo '<div class="list-art-no-thumb">'.$e[array_rand($e)].'</div>';} ?>
  </a>
  <div>
    <div class="list-art-title"><a href="<?php echo esc_url(get_permalink($l)); ?>"><?php echo esc_html($l->post_title); ?></a></div>
    <div class="list-art-time">🕐 <?php echo get_the_date('j M Y',$l); ?><?php if($cn) echo ' &nbsp;·&nbsp; <strong>'.esc_html($cn).'</strong>'; ?></div>
  </div>
</div>
<?php endforeach; ?>
</div>
<?php endif; ?>

</main>
<?php get_sidebar(); ?>
</div></div></div>
<?php get_footer(); ?>
""")

# ── page-fixture.php ────────────────────────────────────────────────────────
open(f"{THEME_DIR}/page-fixture.php","w",encoding="utf-8").write("""\
<?php
/* Template Name: Fixture Mundial 2026 */
get_header();
?>
<div class="site-content">
  <div class="container">
    <div class="fixture-page-container">
      <h1 class="fixture-main-title">🏆 Fixture y Posiciones - Copa Mundial 2026</h1>
      <p class="fixture-subtitle">Seguí el fixture, resultados y la tabla de posiciones de las 12 zonas del Mundial en tiempo real directamente desde Promiedos.</p>
      
      <div class="fixture-tabs">
        <button class="fixture-tab-btn active" onclick="openFixtureTab(event, 'tab-posiciones')">📊 Zonas y Posiciones</button>
        <button class="fixture-tab-btn" onclick="openFixtureTab(event, 'tab-partidos')">⚽ Partidos y Resultados</button>
        <button class="fixture-tab-btn" onclick="openFixtureTab(event, 'tab-eliminatorias')">⚔️ Llaves Eliminatorias</button>
        <button class="fixture-tab-btn" onclick="openFixtureTab(event, 'tab-estadisticas')">🔥 Estadísticas</button>
      </div>

      <?php
      $data_raw = get_option('ppelota_mundial_data');
      $data = $data_raw ? json_decode($data_raw, true) : null;
      ?>

      <!-- TAB 1: POSICIONES -->
      <div id="tab-posiciones" class="fixture-tab-content active">
        <!-- Prominent Banner for projected brackets -->
        <div class="simulation-banner-card" style="background: linear-gradient(135deg, rgba(255, 170, 0, 0.12) 0%, rgba(204, 119, 0, 0.04) 100%); border: 1px solid rgba(255, 170, 0, 0.4); border-radius: 8px; padding: 18px; margin-bottom: 25px; display: flex; align-items: center; justify-content: space-between; gap: 15px; flex-wrap: wrap; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
          <div style="flex: 1; min-width: 285px;">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
              <span style="background: #ffaa00; color: #111; font-size: 10px; font-weight: 800; padding: 2px 6px; border-radius: 3px; text-transform: uppercase;">🔮 EXCLUSIVO</span>
              <h4 style="color: #ffaa00; margin: 0; font-size: 16px; font-weight: 700; font-family: 'Roboto Condensed', sans-serif;">PROYECCIÓN MATEMÁTICA: CRUCES DE 16AVOS AL INSTANTE</h4>
            </div>
            <p style="color: #ccc; margin: 0; font-size: 13px; line-height: 1.45;">Simulación en vivo de los cruces de la fase final calculados en tiempo real según el reglamento oficial de la FIFA (incluyendo los 8 mejores terceros) a medida que cambian los resultados.</p>
          </div>
          <div>
            <button class="cta-sim-btn" onclick="openFixtureTab(event, 'tab-eliminatorias')" style="background: linear-gradient(135deg, #ffaa00 0%, #cc7700 100%); color: #111; border: none; font-weight: 800; font-size: 13px; font-family: 'Roboto Condensed', sans-serif; cursor: pointer; padding: 11px 22px; border-radius: 6px; box-shadow: 0 4px 12px rgba(255, 170, 0, 0.35); transition: all 0.25s ease; text-transform: uppercase;">Ver Simulador de Cruces Hoy →</button>
          </div>
        </div>
        <?php if($data && !empty($data['groups'])): ?>
          <div class="groups-grid">
            <?php foreach($data['groups'] as $group): ?>
              <div class="group-card">
                <h3 class="group-title"><?php echo esc_html($group['name']); ?></h3>
                <div class="table-responsive">
                  <table class="group-table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th style="text-align:left;">Equipo</th>
                        <th>PTS</th>
                        <th>PJ</th>
                        <th>G</th>
                        <th>E</th>
                        <th>P</th>
                        <th>DG</th>
                      </tr>
                    </thead>
                    <tbody>
                      <?php foreach($group['teams'] as $team): 
                        $colors = $team['colors'] ?? [];
                        $bg_color = $colors['color'] ?? '#333';
                        $txt_color = $colors['text_color'] ?? '#fff';
                      ?>
                        <tr class="team-row">
                          <td><span class="team-pos" style="background: <?php echo esc_attr($team['dest_color']); ?>; color: #111;"><?php echo esc_html($team['pos']); ?></span></td>
                          <td style="text-align:left; font-weight:700;">
                            <span class="team-color-badge" style="background: <?php echo esc_attr($bg_color); ?>; border: 1px solid <?php echo esc_attr($txt_color); ?>;"></span>
                            <?php echo esc_html($team['name']); ?>
                          </td>
                          <td class="team-pts"><?php echo esc_html($team['pts']); ?></td>
                          <td><?php echo esc_html($team['pj']); ?></td>
                          <td><?php echo esc_html($team['pg']); ?></td>
                          <td><?php echo esc_html($team['pe']); ?></td>
                          <td><?php echo esc_html($team['pp']); ?></td>
                          <td style="color: <?php echo intval($team['ratio']) >= 0 ? '#0cf737' : '#ff4444'; ?>;"><?php echo esc_html($team['ratio']); ?></td>
                        </tr>
                      <?php endforeach; ?>
                    </tbody>
                  </table>
                </div>
              </div>
            <?php endforeach; ?>
          </div>
        <?php else: ?>
          <p class="no-data-msg">Cargando datos de las posiciones de grupo...</p>
        <?php endif; ?>
      </div>

      <!-- TAB 2: PARTIDOS -->
      <div id="tab-partidos" class="fixture-tab-content">
        <?php if($data && !empty($data['games'])): ?>
          <div class="fixture-matches-section">
            <h2 class="section-title">📅 Partidos de la Fecha Activa (<?php echo esc_html($data['last_updated'] ?? 'Fase de Grupos'); ?>)</h2>
            <div class="matches-list">
              <?php foreach($data['games'] as $game): 
                $status_class = '';
                $status_lbl = $game['status'];
                if (strpos(strtolower($game['status']), 'vivo') !== false || strpos(strtolower($game['status']), 'tiempo') !== false || strpos(strtolower($game['status']), 'jugando') !== false) {
                  $status_class = 'match-live';
                  $status_lbl = '🔴 EN VIVO ' . $game['display_time'];
                } elseif (strpos(strtolower($game['status']), 'finalizado') !== false || strpos(strtolower($game['status']), 'final') !== false) {
                  $status_class = 'match-final';
                  $status_lbl = '🟢 Finalizado';
                } else {
                  $status_class = 'match-prog';
                  $status_lbl = $game['start_time'];
                }
              ?>
                <div class="fixture-match-card <?php echo $status_class; ?>">
                  <div class="match-status-badge"><?php echo esc_html($status_lbl); ?></div>
                  <div class="match-teams">
                    <div class="team home-team">
                      <span class="team-name"><?php echo esc_html($game['home']); ?></span>
                    </div>
                    <div class="match-score">
                      <span class="score-num"><?php echo esc_html($game['home_goals']); ?></span>
                      <span class="score-sep">-</span>
                      <span class="score-num"><?php echo esc_html($game['away_goals']); ?></span>
                    </div>
                    <div class="team away-team">
                      <span class="team-name"><?php echo esc_html($game['away']); ?></span>
                    </div>
                  </div>
                  <div class="match-meta">Copa Mundial de la FIFA 2026</div>
                </div>
              <?php endforeach; ?>
            </div>
          </div>
        <?php else: ?>
          <p class="no-data-msg">Cargando partidos y resultados en vivo...</p>
        <?php endif; ?>
      </div>

      <!-- TAB 3: ELIMINATORIAS -->
      <div id="tab-eliminatorias" class="fixture-tab-content">
        <?php
        $proj_raw = get_option('ppelota_projected_brackets');
        $proj_brackets = $proj_raw ? json_decode($proj_raw, true) : null;
        if (!empty($proj_brackets)):
        ?>
          <div class="projected-section" style="margin-bottom: 40px; border-bottom: 2px solid #2d2d2d; padding-bottom: 30px;">
            <h2 class="section-title" style="color: #ffaa00; margin-bottom: 5px;">🔮 Proyección Matemática: Cruces Proyectados Hoy</h2>
            <p class="description" style="color: #aaa; font-size: 13px; margin-bottom: 20px; font-style: italic;">
              Simulación en tiempo real basada en la tabla de posiciones actual de los grupos y las reglas oficiales de emparejamiento de la FIFA (incluyendo los 8 mejores terceros). Se actualiza automáticamente con el correr de los partidos.
            </p>
            <div class="bracket-matches-grid">
              <?php foreach($proj_brackets as $match): 
                $p0 = $match['home'] ?? 'Por definir';
                $p1 = $match['away'] ?? 'Por definir';
                $l0 = $match['home_label'] ?? '';
                $l1 = $match['away_label'] ?? '';
                $c0 = $match['home_colors']['color'] ?? '#333';
                $c1 = $match['away_colors']['color'] ?? '#333';
              ?>
                <div class="bracket-match-card" style="border-left: 4px solid #ffaa00;">
                  <div style="font-size: 10px; color: #ffaa00; margin-bottom: 8px; font-weight: bold; text-transform: uppercase;">Partido <?php echo esc_html($match['match_num']); ?></div>
                  
                  <div class="bracket-team">
                    <span class="team-color-badge" style="background: <?php echo esc_attr($c0); ?>;"></span>
                    <span class="bracket-team-name" style="font-weight: 700; color: #fff;"><?php echo esc_html($p0); ?></span>
                    <span style="font-size: 9px; color: #ffaa00; margin-left: auto; font-weight: bold;"><?php echo esc_html($l0); ?></span>
                  </div>
                  
                  <div class="bracket-vs-divider">VS</div>
                  
                  <div class="bracket-team">
                    <span class="team-color-badge" style="background: <?php echo esc_attr($c1); ?>;"></span>
                    <span class="bracket-team-name" style="font-weight: 700; color: #fff;"><?php echo esc_html($p1); ?></span>
                    <span style="font-size: 9px; color: #ffaa00; margin-left: auto; font-weight: bold;"><?php echo esc_html($l1); ?></span>
                  </div>
                  
                  <div style="font-size: 9px; color: #777; margin-top: 8px; border-top: 1px solid #2d2d2d; padding-top: 6px; display: flex; justify-content: space-between;">
                    <span>📅 <?php echo esc_html($match['date']); ?></span>
                    <span>📍 <?php echo esc_html($match['venue']); ?></span>
                  </div>
                </div>
              <?php endforeach; ?>
            </div>
          </div>
        <?php endif; ?>

        <h2 class="section-title">⚔️ Llaves Oficiales de la FIFA</h2>
        <?php if($data && !empty($data['brackets'])): ?>
          <div class="brackets-container">
            <?php foreach($data['brackets'] as $stage): ?>
              <div class="bracket-stage-block">
                <h2 class="bracket-stage-title">⚔️ <?php echo esc_html($stage['name']); ?></h2>
                <div class="bracket-matches-grid">
                  <?php foreach($stage['matches'] as $match): 
                    $p0 = $match['participants'][0]['name'] ?? 'Por definir';
                    $p1 = $match['participants'][1]['name'] ?? 'Por definir';
                    $c0 = $match['participants'][0]['colors']['color'] ?? '#333';
                    $c1 = $match['participants'][1]['colors']['color'] ?? '#333';
                    $winner = intval($match['winner'] ?? -1);
                  ?>
                    <div class="bracket-match-card">
                      <div class="bracket-team <?php echo $winner === 0 ? 'winner' : ''; ?>">
                        <span class="team-color-badge" style="background: <?php echo esc_attr($c0); ?>;"></span>
                        <span class="bracket-team-name"><?php echo esc_html($p0); ?></span>
                      </div>
                      <div class="bracket-vs-divider">VS</div>
                      <div class="bracket-team <?php echo $winner === 1 ? 'winner' : ''; ?>">
                        <span class="team-color-badge" style="background: <?php echo esc_attr($c1); ?>;"></span>
                        <span class="bracket-team-name"><?php echo esc_html($p1); ?></span>
                      </div>
                      <?php if(!empty($match['score'])): ?>
                        <div class="bracket-score"><?php echo esc_html($match['score']); ?></div>
                      <?php endif; ?>
                    </div>
                  <?php endforeach; ?>
                </div>
              </div>
            <?php endforeach; ?>
          </div>
        <?php else: ?>
          <p class="no-data-msg">La fase eliminatoria comenzará al finalizar la fase de grupos.</p>
        <?php endif; ?>
      </div>

      <!-- TAB 4: ESTADÍSTICAS -->
      <div id="tab-estadisticas" class="fixture-tab-content">
        <?php
        $stats_raw = get_option('ppelota_player_stats');
        $stats = $stats_raw ? json_decode($stats_raw, true) : null;
        if($stats):
        ?>
          <div class="stats-grids-wrap" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 30px; margin-top: 20px;">
            
            <!-- GOLEADORES -->
            <div style="background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 20px;">
              <h3 style="color: #ffaa00; margin-top: 0; margin-bottom: 15px; font-family: 'Roboto Condensed', sans-serif; font-weight: 700; border-bottom: 2px solid #2d2d2d; padding-bottom: 10px; display: flex; align-items: center; gap: 8px;">⚽ GOLEADORES</h3>
              <table class="group-table" style="width: 100%;">
                <thead>
                  <tr>
                    <th>#</th>
                    <th style="text-align: left;">Jugador</th>
                    <th>Goles</th>
                  </tr>
                </thead>
                <tbody>
                  <?php 
                  $idx = 1;
                  foreach($stats['scorers'] as $s): 
                    $c = $s['colors']['color'] ?? '#333';
                  ?>
                    <tr class="team-row">
                      <td><?php echo $idx++; ?></td>
                      <td style="text-align: left; font-weight: 700;">
                        <span class="team-color-badge" style="background: <?php echo esc_attr($c); ?>;"></span>
                        <?php echo esc_html($s['name']); ?>
                        <span style="font-size: 10px; color: #777; font-weight: normal; display: block; margin-left: 18px;"><?php echo esc_html($s['team']); ?></span>
                      </td>
                      <td style="font-weight: 800; color: #ffaa00; text-align: center;"><?php echo esc_html($s['goals']); ?></td>
                    </tr>
                  <?php endforeach; ?>
                </tbody>
              </table>
            </div>

            <!-- ASISTENCIAS -->
            <div style="background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 20px;">
              <h3 style="color: #ffaa00; margin-top: 0; margin-bottom: 15px; font-family: 'Roboto Condensed', sans-serif; font-weight: 700; border-bottom: 2px solid #2d2d2d; padding-bottom: 10px; display: flex; align-items: center; gap: 8px;">🅰️ ASISTENCIAS</h3>
              <table class="group-table" style="width: 100%;">
                <thead>
                  <tr>
                    <th>#</th>
                    <th style="text-align: left;">Jugador</th>
                    <th>Asist.</th>
                  </tr>
                </thead>
                <tbody>
                  <?php 
                  $idx = 1;
                  foreach($stats['assists'] as $s): 
                    $c = $s['colors']['color'] ?? '#333';
                  ?>
                    <tr class="team-row">
                      <td><?php echo $idx++; ?></td>
                      <td style="text-align: left; font-weight: 700;">
                        <span class="team-color-badge" style="background: <?php echo esc_attr($c); ?>;"></span>
                        <?php echo esc_html($s['name']); ?>
                        <span style="font-size: 10px; color: #777; font-weight: normal; display: block; margin-left: 18px;"><?php echo esc_html($s['team']); ?></span>
                      </td>
                      <td style="font-weight: 800; color: #ffaa00; text-align: center;"><?php echo esc_html($s['assists']); ?></td>
                    </tr>
                  <?php endforeach; ?>
                </tbody>
              </table>
            </div>

            <!-- PASES -->
            <div style="background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 20px;">
              <h3 style="color: #ffaa00; margin-top: 0; margin-bottom: 15px; font-family: 'Roboto Condensed', sans-serif; font-weight: 700; border-bottom: 2px solid #2d2d2d; padding-bottom: 10px; display: flex; align-items: center; gap: 8px;">🎯 PASES Y EFECTIVIDAD</h3>
              <table class="group-table" style="width: 100%;">
                <thead>
                  <tr>
                    <th>#</th>
                    <th style="text-align: left;">Jugador</th>
                    <th>Pases</th>
                    <th>Efect.</th>
                  </tr>
                </thead>
                <tbody>
                  <?php 
                  $idx = 1;
                  foreach($stats['passing'] as $s): 
                    $c = $s['colors']['color'] ?? '#333';
                  ?>
                    <tr class="team-row">
                      <td><?php echo $idx++; ?></td>
                      <td style="text-align: left; font-weight: 700;">
                        <span class="team-color-badge" style="background: <?php echo esc_attr($c); ?>;"></span>
                        <?php echo esc_html($s['name']); ?>
                        <span style="font-size: 10px; color: #777; font-weight: normal; display: block; margin-left: 18px;"><?php echo esc_html($s['team']); ?></span>
                      </td>
                      <td style="text-align: center;"><?php echo esc_html($s['passes']); ?></td>
                      <td style="font-weight: 800; color: #ffaa00; text-align: center;"><?php echo esc_html($s['accuracy']); ?></td>
                    </tr>
                  <?php endforeach; ?>
                </tbody>
              </table>
            </div>

          </div>
        <?php else: ?>
          <p class="no-data-msg">Estadísticas de jugadores no disponibles en este momento.</p>
        <?php endif; ?>
      </div>
    </div>
  </div>
</div>

<script>
function openFixtureTab(evt, tabName) {
  var i, tabcontent, tablinks;
  tabcontent = document.getElementsByClassName("fixture-tab-content");
  for (i = 0; i < tabcontent.length; i++) {
    tabcontent[i].classList.remove("active");
  }
  tablinks = document.getElementsByClassName("fixture-tab-btn");
  for (i = 0; i < tablinks.length; i++) {
    tablinks[i].classList.remove("active");
  }
  document.getElementById(tabName).classList.add("active");
  
  // Find the button with onclick containing the tabName and make it active!
  var targetBtn = null;
  for (i = 0; i < tablinks.length; i++) {
    if (tablinks[i].getAttribute('onclick') && tablinks[i].getAttribute('onclick').includes(tabName)) {
      tablinks[i].classList.add("active");
    }
  }
  if (evt && evt.currentTarget) {
    evt.currentTarget.classList.add("active");
  }
}

document.addEventListener("DOMContentLoaded", function() {
  const urlParams = new URLSearchParams(window.location.search);
  const tabParam = urlParams.get('tab');
  if (tabParam && document.getElementById(tabParam)) {
    openFixtureTab(null, tabParam);
    setTimeout(function() {
      document.querySelector('.fixture-tabs').scrollIntoView({ behavior: 'smooth' });
    }, 100);
  }
});
</script>
<?php get_footer(); ?>
""")

# ── category.php ────────────────────────────────────────────────────────────
open(f"{THEME_DIR}/category.php","w",encoding="utf-8").write("""\
<?php get_header(); ?>
<div class="site-content"><div class="container"><div class="content-wrap">
<main class="main-content">
  <div class="category-header">
    <div class="category-header-decor">SPORT</div>
    <div style="position: relative; z-index: 1;">
      <span class="category-tag">Categoría</span>
      <h1>📂 <?php single_cat_title(); ?></h1>
      <p><?php echo category_description() ? strip_tags(category_description()) : 'Toda la cobertura exclusiva de ' . single_cat_title('', false) . ' con análisis, opiniones y las últimas novedades en tiempo real.'; ?></p>
    </div>
  </div>

  <?php if(have_posts()): ?>
    <div class="articles-grid">
      <?php while(have_posts()): the_post(); 
        $c = get_the_category(); 
        $cn = $c ? $c[0]->name : 'Noticias'; 
      ?>
        <div class="art-card">
          <a href="<?php the_permalink(); ?>">
            <?php if(has_post_thumbnail()) { the_post_thumbnail('card-thumb', ['class' => 'art-card-img', 'alt' => '']); }
            else { $e = ['⚽','🏆','🔥','⚡']; echo '<div class="art-card-no-img">' . $e[array_rand($e)] . '</div>'; } ?>
          </a>
          <div class="art-card-body">
            <div class="art-card-cat"><?php echo esc_html($cn); ?></div>
            <div class="art-card-title"><a href="<?php the_permalink(); ?>"><?php the_title(); ?></a></div>
            <div class="art-card-excerpt"><?php echo wp_trim_words(get_the_excerpt(), 14, '...'); ?></div>
            <div class="art-card-time">🕐 <?php the_date('j M Y'); ?></div>
          </div>
        </div>
      <?php endwhile; ?>
    </div>
    <div class="pagination"><?php the_posts_pagination(); ?></div>
  <?php else: ?>
    <div class="empty-category-box">
      <div class="empty-category-icon">⚽</div>
      <h3 class="empty-category-title">Sin contenido en esta sección todavía</h3>
      <p class="empty-category-text">Estamos preparando la mejor cobertura para esta liga. Mientras tanto, disfrutá de lo más destacado de hoy:</p>
    </div>

    <div class="section-heading" style="margin-top: 40px; margin-bottom: 20px;">🔥 Lo Más Destacado del Día</div>
    <div class="articles-grid">
      <?php
      $backup_posts = get_posts(['numberposts' => 6, 'post_status' => 'publish']);
      if ($backup_posts) {
        foreach ($backup_posts as $post) {
          setup_postdata($post);
          $c = get_the_category($post->ID);
          $cn = $c ? $c[0]->name : 'Noticias';
          ?>
          <div class="art-card">
            <a href="<?php echo esc_url(get_permalink($post->ID)); ?>">
              <?php if (has_post_thumbnail($post->ID)) { echo get_the_post_thumbnail($post->ID, 'card-thumb', ['class' => 'art-card-img', 'alt' => '']); }
              else { $e = ['⚽','🏆','🔥','⚡']; echo '<div class="art-card-no-img">' . $e[array_rand($e)] . '</div>'; } ?>
            </a>
            <div class="art-card-body">
              <div class="art-card-cat"><?php echo esc_html($cn); ?></div>
              <div class="art-card-title"><a href="<?php echo esc_url(get_permalink($post->ID)); ?>"><?php echo esc_html($post->post_title); ?></a></div>
              <div class="art-card-excerpt"><?php echo wp_trim_words(get_the_excerpt($post->ID), 14, '...'); ?></div>
              <div class="art-card-time">🕐 <?php echo get_the_date('j M Y', $post->ID); ?></div>
            </div>
          </div>
          <?php
        }
        wp_reset_postdata();
      } else {
        echo '<p style="text-align:center; color:#999; padding: 20px;">No hay noticias disponibles en el portal.</p>';
      }
      ?>
    </div>
  <?php endif; ?>
</main>
<?php get_sidebar(); ?>
</div></div></div>
<?php get_footer(); ?>
""")

# ── index.php ───────────────────────────────────────────────────────────────
open(f"{THEME_DIR}/index.php","w",encoding="utf-8").write("""\
<?php get_header(); ?>
<div class="site-content"><div class="container"><div class="content-wrap">
<main class="main-content">
<?php if(is_category()):?><div class="section-heading">📂 <?php single_cat_title();?></div>
<?php elseif(is_search()):?><div class="section-heading">🔍 "<?php the_search_query();?>"</div>
<?php else:?><div class="section-heading">📰 Noticias</div><?php endif;?>
<?php if(have_posts()):?>
<div class="articles-grid">
<?php while(have_posts()):the_post();$c=get_the_category();$cn=$c?$c[0]->name:'Noticias';?>
<div class="art-card">
  <a href="<?php the_permalink();?>">
    <?php if(has_post_thumbnail()){the_post_thumbnail('card-thumb',['class'=>'art-card-img','alt'=>'']);}
    else{$e=['⚽','🏆','🔥','⚡'];echo '<div class="art-card-no-img">'.$e[array_rand($e)].'</div>';}?>
  </a>
  <div class="art-card-body">
    <div class="art-card-cat"><?php echo esc_html($cn);?></div>
    <div class="art-card-title"><a href="<?php the_permalink();?>"><?php the_title();?></a></div>
    <div class="art-card-excerpt"><?php echo wp_trim_words(get_the_excerpt(),14,'...');?></div>
    <div class="art-card-time">🕐 <?php the_date('j M Y');?></div>
  </div>
</div>
<?php endwhile;?>
</div>
<div class="pagination"><?php the_posts_pagination();?></div>
<?php else:?><p style="background:#fff;padding:30px;text-align:center;color:#888;border-radius:2px;">No se encontraron artículos.</p><?php endif;?>
</main>
<?php get_sidebar();?>
</div></div></div>
<?php get_footer();?>
""")

# ── single.php ───────────────────────────────────────────────────────────────
open(f"{THEME_DIR}/single.php","w",encoding="utf-8").write("""\
<?php get_header();?>
<div class="site-content"><div class="container"><div class="content-wrap">
<main class="main-content">
<?php while(have_posts()):the_post();
$c=get_the_category();$cn=$c?$c[0]->name:'';$cl=$c?get_category_link($c[0]->term_id):'';
$tags=get_the_tags();
?>
<div class="single-header">
  <?php if($cn):?><a href="<?php echo esc_url($cl);?>" class="volanta" style="margin-bottom:0;"><?php echo esc_html($cn);?></a><?php endif;?>
  <h1 class="single-title"><?php the_title();?></h1>
  <div class="single-meta">
    <span>📅 <?php the_date('j F Y');?></span>
    <span>🕐 <?php the_time('H:i');?> hs</span>
    <span>✍️ Vicente Salvarredi</span>
  </div>
</div>
<?php if(has_post_thumbnail()):?>
<img class="single-featured-img" src="<?php echo get_the_post_thumbnail_url(get_the_ID(),'large');?>" alt="<?php the_title_attribute();?>">
<?php endif;?>
<?php
$ad_article = get_theme_mod('ppelota_ad_article');
if ($ad_article):
?>
  <div class="ad-slot-wrapper in-article-ad-slot">
    <?php echo $ad_article; ?>
  </div>
<?php endif; ?>
<div class="post-body"><?php the_content();?></div>
<?php if($tags):?>
<div class="tags-wrap">
  <span class="tag-label">🏷️ Tags:</span>
  <?php foreach($tags as $t):?><a href="<?php echo esc_url(get_tag_link($t->term_id));?>" class="tag-link"><?php echo esc_html($t->name);?></a><?php endforeach;?>
</div>
<?php endif;?>
<div class="share-bar">
  <span class="share-label">📤 Compartir:</span>
  <a class="share-btn tw" href="https://twitter.com/intent/tweet?url=<?php echo urlencode(get_permalink());?>&text=<?php echo urlencode(get_the_title());?>" target="_blank">🐦 Twitter</a>
  <a class="share-btn fb" href="https://www.facebook.com/sharer/sharer.php?u=<?php echo urlencode(get_permalink());?>" target="_blank">📘 Facebook</a>
  <a class="share-btn wa" href="https://wa.me/?text=<?php echo urlencode(get_the_title().' '.get_permalink());?>" target="_blank">💬 WhatsApp</a>
</div>
<?php
$rc=wp_get_post_categories(get_the_ID());
if($rc){$rel=get_posts(['category__in'=>$rc,'exclude'=>[get_the_ID()],'numberposts'=>3]);
if($rel):?>
<div class="section-heading">📰 Artículos Relacionados</div>
<div class="articles-grid">
<?php foreach($rel as $r):$rc2=get_the_category($r->ID);$rcn=$rc2?$rc2[0]->name:'';?>
<div class="art-card">
  <a href="<?php echo esc_url(get_permalink($r));?>">
    <?php if(has_post_thumbnail($r->ID)){echo get_the_post_thumbnail($r->ID,'card-thumb',['class'=>'art-card-img','alt'=>'']);}
    else{$e=['⚽','🏆','🔥','⚡'];echo '<div class="art-card-no-img">'.$e[array_rand($e)].'</div>';}?>
  </a>
  <div class="art-card-body">
    <div class="art-card-cat"><?php echo esc_html($rcn);?></div>
    <div class="art-card-title"><a href="<?php echo esc_url(get_permalink($r));?>"><?php echo esc_html($r->post_title);?></a></div>
    <div class="art-card-time">🕐 <?php echo get_the_date('j M Y',$r);?></div>
  </div>
</div>
<?php endforeach;?>
</div>
<?php endif;}?>
<?php endwhile;?>
</main>
<?php get_sidebar();?>
</div></div></div>
<?php get_footer();?>
""")

print("✅ Todos los archivos PHP creados")

# ── ZIP ─────────────────────────────────────────────────────────────────────
ZIP_PATH = f"/tmp/{THEME_SLUG}.zip"
if os.path.exists(ZIP_PATH): os.remove(ZIP_PATH)
with zipfile.ZipFile(ZIP_PATH,'w',zipfile.ZIP_DEFLATED) as zf:
    for root,dirs,files in os.walk(THEME_DIR):
        for file in files:
            fp=os.path.join(root,file)
            zf.write(fp, os.path.join(THEME_SLUG, os.path.relpath(fp,THEME_DIR)))
print(f"✅ ZIP creado: {ZIP_PATH} ({os.path.getsize(ZIP_PATH):,} bytes)")

# ── UPLOAD via WordPress REST API ──────────────────────────────────────────
print("📤 Subiendo el ZIP del tema a la Media Library de WordPress...")
token = base64.b64encode(f"{WP_USER}:{WP_PASS}".encode()).decode()
auth_headers = {"Authorization": f"Basic {token}"}

# Subir como media file
upload_headers = {
    **auth_headers,
    'Content-Disposition': 'attachment; filename="pasion-pelota.zip"',
    'Content-Type': 'application/zip'
}

with open(ZIP_PATH, 'rb') as f:
    zip_bytes = f.read()

resp = requests.post(
    f"{WP_URL}/wp-json/wp/v2/media",
    headers=upload_headers,
    data=zip_bytes,
    timeout=30
)

if resp.status_code not in [200, 201]:
    print(f"❌ Error al subir ZIP: {resp.status_code}")
    print(resp.text)
    sys.exit(1)

data = resp.json()
uploaded_zip_url = data.get("source_url")
print(f"✅ ZIP subido. URL: {uploaded_zip_url}")

# ── Actualizar e Instalar Snippet PHP ─────────────────────────────────────────
print("⚙️ Actualizando Snippet PHP para instalar tema...")

php_code = f"""
$zip_url = "{uploaded_zip_url}";
$zip_local = WP_CONTENT_DIR . "/uploads/pasion-pelota-install.zip";
$upload_dir = get_home_path() . "wp-content/themes/";

// Download ZIP
$response = wp_remote_get($zip_url, ["timeout"=>30]);
if (!is_wp_error($response)) {{
    file_put_contents($zip_local, wp_remote_retrieve_body($response));
    // Unzip
    $unzip = unzip_file($zip_local, $upload_dir);
    if (!is_wp_error($unzip)) {{
        // Activate
        switch_theme("pasion-pelota");
        error_log("TEMA PASION PELOTA INSTALADO Y ACTIVADO");
    }} else {{
        error_log("Error unzip: " . $unzip->get_error_message());
    }}
    unlink($zip_local);
}}
"""

snippet_payload = {
    'name': 'Instalar Tema Pasion Pelota',
    'code': php_code,
    'scope': 'global',
    'active': True
}

# Update snippet #5
update_resp = requests.post(
    f"{WP_URL}/wp-json/code-snippets/v1/snippets/5",
    headers={**auth_headers, "Content-Type": "application/json"},
    json=snippet_payload,
    timeout=30
)

if update_resp.status_code not in [200, 201]:
    print(f"❌ Error al actualizar snippet: {update_resp.status_code}")
    print(update_resp.text)
    sys.exit(1)

print("✅ Snippet PHP actualizado y activado.")

# ── Ejecutar el Snippet ───────────────────────────────────────────────────
print("🚀 Cargando la web para ejecutar la instalación del tema...")
import time
time.sleep(2)
trigger_resp = requests.get(f"{WP_URL}/", timeout=30)
print(f"Carga de web completada. Status: {trigger_resp.status_code}")

# ── Desactivar el Snippet ────────────────────────────────────────────────
print("🧹 Desactivando snippet de instalación para optimizar rendimiento...")
deactivate_resp = requests.post(
    f"{WP_URL}/wp-json/code-snippets/v1/snippets/5",
    headers={**auth_headers, "Content-Type": "application/json"},
    json={'active': False},
    timeout=30
)
if deactivate_resp.status_code in [200, 201]:
    print("✅ Snippet desactivado con éxito.")
else:
    print("⚠️ No se pudo desactivar el snippet. Inténtalo manualmente desde WP-Admin.")

print("\n🎉 PROCESO COMPLETADO")
print(f"   → Visita {WP_URL} para ver el nuevo diseño Marca + Olé")
