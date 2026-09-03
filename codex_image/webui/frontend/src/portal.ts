
import { getLegacyBridge } from "./state";

// 预设高频场景模板
const SCENE_TEMPLATES: Record<string, { prompt: string; ratio?: string }> = {
  product: {
    prompt: "高端商业产品静物摄影，纯净极简大理石展台，清透水滴与自然晨光，柔和丁达尔光束，细腻金属反光与陶瓷质感，商业广告级构图，8K画质",
    ratio: "1:1",
  },
  branding: {
    prompt: "现代高端科技品牌视觉宣传海报，深蓝色与哑光银色调，流线型几何曲面，发光线条穿透空间，大面积高级留白，商务严谨，未来感",
    ratio: "9:16",
  },
  portrait: {
    prompt: "亚洲干练商务女性高管职业肖像照，身着剪裁合体深色西装，背景为浅虚化现代写字楼落地窗，自信温和微笑，高级影棚伦勃朗柔光",
    ratio: "3:4",
  },
  festival: {
    prompt: "企业新年庆典主视觉KV海报，中国红与鎏金烫金质感，祥云瑞气与立体几何剪纸折扇，喜庆大气，浓郁节日氛围，超高清3D渲染",
    ratio: "16:9",
  },
};

// 精选灵感画廊种子数据
const SEED_GALLERY = [
  {
    image: "/outputs/2026-09-03/20260903044957-b5baa915-image-1.png",
    prompt: "企业智能机器人，商业产品静物摄影背景，纯净的水晶展台，柔和冷白顶光",
    ratio: "9:16",
  },
  {
    image: "/outputs/2026-09-03/20260903045758-a8634a1b-image-1.png",
    prompt: "恒泰具身机器人，商业产品静物摄影背景，纯净的水晶展台与倒影",
    ratio: "9:16",
  },
  {
    image: "/outputs/2026-08-31/20260831012149-c1729900-image-1.png",
    prompt: "现代高端科技品牌视觉宣传海报，深蓝色与哑光银色调，流线型几何曲面，发光线条穿透空间",
    ratio: "9:16",
  },
  {
    image: "/outputs/2026-08-21/20260821031014-c83f3bab-image-1.png",
    prompt: "商务女性高管职业形象大片，影棚柔光轮廓，专业自信神态",
    ratio: "9:16",
  },
];

export function initPortalFeature() {
  const portalView = document.getElementById("portalView");
  const dashboard = document.querySelector<HTMLElement>(".dashboard");
  const sidebar = document.getElementById("sidebar");
  const portalModeBtn = document.getElementById("portalModeBtn");
  const studioModeBtn = document.getElementById("studioModeBtn");

  const portalPromptInput = document.getElementById("portalPromptInput") as HTMLTextAreaElement | null;
  const portalOptimizeBtn = document.getElementById("portalOptimizeBtn");
  const portalOptimizeText = document.getElementById("portalOptimizeText");
  const portalGenerateBtn = document.getElementById("portalGenerateBtn");
  const portalGalleryGrid = document.getElementById("portalGalleryGrid");

  let currentMode: "portal" | "studio" = "portal";

  // 模式切换控制
  const switchMode = (mode: "portal" | "studio") => {
    currentMode = mode;
    if (mode === "portal") {
      portalView?.classList.remove("hidden");
      if (dashboard) dashboard.style.display = "none";
      if (sidebar) sidebar.style.display = "none";
      portalModeBtn?.classList.add("active");
      portalModeBtn?.setAttribute("aria-selected", "true");
      studioModeBtn?.classList.remove("active");
      studioModeBtn?.setAttribute("aria-selected", "false");
    } else {
      portalView?.classList.add("hidden");
      if (dashboard) dashboard.style.display = "";
      if (sidebar) sidebar.style.display = "";
      portalModeBtn?.classList.remove("active");
      portalModeBtn?.setAttribute("aria-selected", "false");
      studioModeBtn?.classList.add("active");
      studioModeBtn?.setAttribute("aria-selected", "true");
    }
  };

  portalModeBtn?.addEventListener("click", () => switchMode("portal"));
  studioModeBtn?.addEventListener("click", () => switchMode("studio"));

  // 快捷标签点击填入
  document.querySelectorAll<HTMLButtonElement>(".portal-tag-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const tag = chip.dataset.tag || "";
      if (!portalPromptInput) return;
      if (portalPromptInput.value.trim()) {
        portalPromptInput.value += `，${tag}`;
      } else {
        portalPromptInput.value = tag;
      }
      portalPromptInput.focus();
    });
  });

  // 场景工坊卡片点击
  document.querySelectorAll<HTMLElement>(".workshop-card").forEach((card) => {
    card.addEventListener("click", () => {
      const scene = card.dataset.scene || "";
      const template = SCENE_TEMPLATES[scene];
      if (template) {
        const bridge = getLegacyBridge();
        bridge.methods.setPromptText?.(template.prompt);
        if (template.ratio) {
          const ratioBtn = document.querySelector<HTMLButtonElement>(`#ratioGroup [data-val="${template.ratio}"]`);
          ratioBtn?.click();
        }
        switchMode("studio");
      }
    });
  });

  // 门户魔盒优化提示词
  portalOptimizeBtn?.addEventListener("click", async () => {
    const text = portalPromptInput?.value.trim() || "";
    if (!text) {
      alert("请先输入一段基础描述，再进行 AI 优化！");
      portalPromptInput?.focus();
      return;
    }

    portalOptimizeBtn.setAttribute("disabled", "true");
    if (portalOptimizeText) portalOptimizeText.textContent = "AI 正在扩写优化中…";

    try {
      const res = await fetch("/api/prompt/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: text }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "优化失败");

      if (portalPromptInput && data.optimized_prompt) {
        portalPromptInput.value = data.optimized_prompt;
      }
      if (portalOptimizeText) portalOptimizeText.textContent = "优化成功！";
      window.setTimeout(() => {
        if (portalOptimizeText) portalOptimizeText.textContent = "✨ 优化提示词";
      }, 2000);
    } catch (err: any) {
      alert(err.message || "请求失败");
      if (portalOptimizeText) portalOptimizeText.textContent = "✨ 优化提示词";
    } finally {
      portalOptimizeBtn.removeAttribute("disabled");
    }
  });

  // 门户魔盒开始生成 -> 切换到工作台并自动触发生成
  portalGenerateBtn?.addEventListener("click", () => {
    const text = portalPromptInput?.value.trim() || "";
    const bridge = getLegacyBridge();
    if (text) {
      bridge.methods.setPromptText?.(text);
    }
    switchMode("studio");
    const runButton = document.getElementById("runButton");
    runButton?.click();
  });

  // 渲染灵感画廊与做同款
  const renderGallery = async () => {
    if (!portalGalleryGrid) return;
    let items = SEED_GALLERY;
    try {
      const res = await fetch("/api/tasks/recent?limit=25");
      const data = await res.json();
      const dynamicItems: any[] = [];
      (data.tasks || []).forEach((t: any) => {
        const thumb = t.branding_thumbnail_url || (Array.isArray(t.thumbnail_urls) && t.thumbnail_urls[0]) || (Array.isArray(t.output_urls) && t.output_urls[0]);
        if (thumb && t.prompt && t.status === "completed") {
          dynamicItems.push({
            image: thumb,
            prompt: t.prompt,
            ratio: t.params?.ratio || "9:16",
          });
        }
      });
      if (dynamicItems.length >= 2) {
        items = dynamicItems.slice(0, 8);
      }
    } catch (e) {
      console.warn("fetch recent tasks for portal gallery error:", e);
    }

    portalGalleryGrid.innerHTML = items.map((item) => `
      <div class="portal-gallery-item">
        <img class="portal-gallery-img" src="${item.image}" alt="" loading="lazy" onerror="this.src='/static/favicon.ico'" />
        <div class="portal-gallery-overlay">
          <div class="portal-gallery-prompt">${item.prompt}</div>
          <button class="portal-reuse-btn" type="button" data-prompt="${item.prompt.replace(/"/g, "&quot;")}" data-ratio="${item.ratio}">
            ✨ 一键做同款
          </button>
        </div>
      </div>
    `).join("");

    portalGalleryGrid.querySelectorAll<HTMLButtonElement>(".portal-reuse-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const prompt = btn.dataset.prompt || "";
        const ratio = btn.dataset.ratio || "";
        const bridge = getLegacyBridge();
        bridge.methods.setPromptText?.(prompt);
        if (ratio) {
          const ratioBtn = document.querySelector<HTMLButtonElement>(`#ratioGroup [data-val="${ratio}"]`);
          ratioBtn?.click();
        }
        switchMode("studio");
      });
    });
  };

  renderGallery();

  // 默认启动为门户模式
  switchMode("portal");
}
