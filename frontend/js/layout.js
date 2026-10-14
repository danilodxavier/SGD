/* Estrutura institucional e acessibilidade (eMAG / WCAG 2.1 AA):
   barra de acessibilidade (alto contraste, tamanho do texto), atalhos [1] a [4], breadcrumb
   e indicação do item de menu atual. Camada apenas visual: não chama a API.
   Carregado no <head> para aplicar contraste e tamanho de texto antes de a página aparecer. */
"use strict";

const Layout = (() => {
  const root = document.documentElement;
  const FONT_STEPS = [87.5, 100, 112.5, 125, 137.5, 150];   // % do tamanho padrão do navegador
  const DEFAULT_STEP = 1;

  const store = {
    get(key) { try { return localStorage.getItem(key); } catch (e) { return null; } },
    set(key, value) { try { localStorage.setItem(key, value); } catch (e) { /* armazenamento indisponível */ } },
  };

  const saved = store.get("a11y-fonte");
  let fontStep = saved === null ? DEFAULT_STEP : Number(saved);
  if (!Number.isInteger(fontStep) || !FONT_STEPS[fontStep]) fontStep = DEFAULT_STEP;

  function applyContrast(on) {
    if (on) root.setAttribute("data-contraste", "alto");
    else root.removeAttribute("data-contraste");
    const btn = document.getElementById("a11y-contraste");
    if (btn) btn.setAttribute("aria-pressed", on ? "true" : "false");
  }

  function applyFont() {
    root.style.fontSize = fontStep === DEFAULT_STEP ? "" : `${FONT_STEPS[fontStep]}%`;
    const minus = document.getElementById("a11y-fonte-menos");
    const plus = document.getElementById("a11y-fonte-mais");
    if (minus) minus.disabled = fontStep === 0;
    if (plus) plus.disabled = fontStep === FONT_STEPS.length - 1;
  }

  // aplica as preferências imediatamente (antes da renderização)
  applyContrast(store.get("a11y-contraste") === "alto");
  applyFont();

  function announce(text) {
    const status = document.getElementById("a11y-status");
    if (!status) return;
    status.textContent = "";
    setTimeout(() => { status.textContent = text; }, 50);
  }

  function setFont(step) {
    fontStep = Math.max(0, Math.min(FONT_STEPS.length - 1, step));
    store.set("a11y-fonte", String(fontStep));
    applyFont();
    announce(`Tamanho do texto: ${FONT_STEPS[fontStep]}%.`);
  }

  function isVisible(el) {
    return !!el && el.getClientRects().length > 0 && getComputedStyle(el).visibility !== "hidden";
  }

  function focusTarget(el) {
    if (!el) return;
    if (!el.hasAttribute("tabindex") && !/^(A|BUTTON|INPUT|SELECT|TEXTAREA)$/.test(el.tagName)) {
      el.setAttribute("tabindex", "-1");
    }
    el.focus();
    if (el.scrollIntoView) el.scrollIntoView({ block: "start" });
  }

  // destinos dos atalhos [1] conteúdo, [2] menu, [3] busca, [4] rodapé
  function goTo(target) {
    if (target === "rodape") { focusTarget(document.getElementById("rodape")); return; }
    // na tela de acesso não há menu nem busca: vai ao primeiro campo do formulário
    const auth = document.getElementById("auth-screen");
    if (isVisible(auth)) { focusTarget(auth.querySelector(".auth-form:not(.hidden) input") || auth); return; }
    const menu = document.getElementById("menu");
    if (target === "menu" && menu) {
      focusTarget(menu.querySelector('.nav-item[aria-current="page"]') || menu.querySelector(".nav-item"));
      return;
    }
    const ask = document.getElementById("ask-input");
    if (target === "busca" && ask && typeof showView === "function") {
      showView("perguntas");
      focusTarget(ask);
      return;
    }
    focusTarget(document.getElementById("conteudo"));   // conteúdo (e destino padrão quando o item não existe na página)
  }

  // chamado por showView (app.js) a cada troca de tela
  function onView(name) {
    let label = "";
    document.querySelectorAll("#menu .nav-item").forEach((b) => {
      const current = b.dataset.view === name;
      if (current) { b.setAttribute("aria-current", "page"); label = b.textContent.trim(); }
      else b.removeAttribute("aria-current");
    });
    const crumb = document.getElementById("breadcrumb-atual");
    const home = document.getElementById("breadcrumb-inicio");
    if (crumb) {
      crumb.textContent = label;
      crumb.parentElement.classList.toggle("hidden", name === "dashboard");
    }
    if (home) {
      // na página inicial o próprio "Início" é a página atual
      if (name === "dashboard") home.setAttribute("aria-current", "page");
      else home.removeAttribute("aria-current");
    }
    document.title = label && name !== "dashboard"
      ? `${label} — Agente de Inteligência Documental` : "Agente de Inteligência Documental";
  }

  function init() {
    applyContrast(root.getAttribute("data-contraste") === "alto");
    applyFont();

    const contrast = document.getElementById("a11y-contraste");
    if (contrast) contrast.addEventListener("click", () => {
      const on = root.getAttribute("data-contraste") !== "alto";
      store.set("a11y-contraste", on ? "alto" : "normal");
      applyContrast(on);
      announce(on ? "Alto contraste ativado." : "Alto contraste desativado.");
    });
    const plus = document.getElementById("a11y-fonte-mais");
    const minus = document.getElementById("a11y-fonte-menos");
    const reset = document.getElementById("a11y-fonte-padrao");
    if (plus) plus.addEventListener("click", () => setFont(fontStep + 1));
    if (minus) minus.addEventListener("click", () => setFont(fontStep - 1));
    if (reset) reset.addEventListener("click", () => setFont(DEFAULT_STEP));

    document.querySelectorAll("[data-atalho]").forEach((a) => a.addEventListener("click", (ev) => {
      ev.preventDefault();
      goTo(a.dataset.atalho);
    }));

    const home = document.getElementById("breadcrumb-inicio");
    if (home) home.addEventListener("click", (ev) => {
      ev.preventDefault();
      if (typeof showView === "function") showView("dashboard");
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();

  return { onView, goTo };
})();
