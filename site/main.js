const copyValues = {
  install: "codex plugin marketplace add liyanqing90/rootloom\ncodex plugin add rootloom@rootloom",
  marketplace: "codex plugin marketplace add liyanqing90/rootloom",
  plugin: "codex plugin add rootloom@rootloom",
};

const messages = {
  en: {
    pageTitle: "Rootloom — Make code changes you can explain",
    pageDescription: "Rootloom is a native OpenAI Codex engineering plugin with an Agent Plugins preview for portable Change, Review, and Project Guidance.",
    skip: "Skip to main content",
    menu: "Menu",
    openMenu: "Open navigation",
    closeMenu: "Close navigation",
    navWhy: "Why Rootloom",
    navHow: "How it works",
    navWorkflows: "Workflows",
    navDocs: "Docs",
    github: "GitHub",
    heroTitle: "Make code changes you can explain.",
    heroBody: "Rootloom gives coding agents a disciplined path from repository evidence to a focused change and verification you can inspect.",
    installCta: "Install Rootloom",
    viewGithub: "View on GitHub",
    copyBoth: "Copy both",
    heroNote: "These commands install the native Codex plugin. A separate Agent Plugins preview provides portable Change, Review, and Project Guidance.",
    heroAlt: "A black cat at a loom weaving tangled risks, defects, and context into a checked result",
    problemTitle: "Most coding failures happen before the diff.",
    problemBody: "An agent can write plausible code at the wrong boundary, run one convenient test, then report more certainty than the evidence supports. Rootloom changes that sequence.",
    failureOneTitle: "Patch the symptom",
    failureOneBody: "The error line gets a guard; the component that owns the behavior stays broken.",
    failureTwoTitle: "Test the happy path",
    failureTwoBody: "Reconnect passes while cancellation and clean disconnect quietly drift.",
    failureThreeTitle: "Report a result",
    failureThreeBody: "Suggested checks and executed checks blur into the same sentence.",
    middleTitle: "Rootloom makes the missing middle visible.",
    middleBody: "The patch is one step in an engineering decision, not the whole decision.",
    flowAria: "Rootloom engineering flow from request to verified report",
    flowRequest: "Request",
    flowEvidence: "Repository evidence",
    flowScope: "Risk and scope",
    flowOwner: "Owning boundary",
    flowChange: "Focused change",
    flowReport: "Verified report",
    workflowTitle: "From request to evidence, one owned step at a time.",
    workflowBody: "Ordinary work stays on the repository's normal edit-and-test path. Rootloom supplies the discipline around it.",
    stepOneTitle: "Read the project",
    stepOneBody: "Inspect source, tests, local rules, and existing work before editing.",
    stepTwoTitle: "Set risk and scope",
    stepTwoBody: "Match the workflow to the blast radius and name what should not change.",
    stepThreeTitle: "Find the owner",
    stepThreeBody: "For a defect, trace the trigger to the boundary that owns the invariant.",
    stepFourTitle: "Make the focused change",
    stepFourBody: "Use the repository's architecture and preserve unrelated work.",
    stepFiveTitle: "Verify and report",
    stepFiveBody: "Exercise the main path, the invariant, and an adjacent path. Name what actually ran.",
    workflowAlt: "Rootloom loom diagram: risk, defects, and context are processed with evidence, a contract, and tests into a verified result",
    workflowCaption: "The illustrated loom is the product model: messy inputs become a reviewable result through evidence, scope, and tests.",
    workflowsTitle: "One Core, four public entries.",
    workflowsBody: "Change routes risk and evidence modes internally, so users choose by intent instead of governance machinery.",
    choiceChangeTitle: "Daily change",
    choiceChangeBody: "Build, fix, or refactor ordinary code with scoped verification.",
    choiceReviewTitle: "Review only",
    choiceReviewBody: "Inspect a diff, PR, migration, or design without changing files.",
    choiceRiskTitle: "Project guidance",
    choiceRiskBody: "Seed, refresh, refine, or validate concise AGENTS.md guidance.",
    choiceSetupTitle: "Setup",
    choiceSetupBody: "Install, upgrade, inspect, or roll back optional global guidance and Autonomy Rules.",
    optionalPrefix: "Need a governed change or machine-readable evidence bundle?",
    optionalSuffix: "loads that mode explicitly and only when needed.",
    allSkills: "See all four Skills",
    evidenceTitle: "Completion should say what happened.",
    evidenceBody: "Rootloom keeps plans, command results, repository state, and human judgment as separate facts.",
    evidenceOneTitle: "Plans stay labeled as plans.",
    evidenceOneBody: "A generated verification command is a suggestion until it actually runs.",
    evidenceTwoTitle: "State is checked after commands finish.",
    evidenceTwoBody: "Exit code 0 is insufficient when the repository or captured evidence changed.",
    evidenceThreeTitle: "Evidence supports judgment.",
    evidenceThreeBody: "It makes a review inspectable; it does not prove that code is correct or secure.",
    caseBody: "A real Rootloom regression passed its command and still failed review because repository state changed afterward.",
    readCase: "Read the case study",
    installTitle: "Start with the native Codex plugin.",
    installBody: "Use these commands for the complete Codex experience. Agent Plugins-compatible clients can load the three-Skill preview from portable/rootloom; see the preview guide below.",
    installOneTitle: "Add the marketplace",
    installTwoTitle: "Install Rootloom",
    installThreeTitle: "Open a new task",
    promptExample: "Fix the reconnect race and verify reconnect, clean disconnect, and cancellation.",
    copy: "Copy",
    copied: "Copied",
    copiedStatus: "Command copied to the clipboard.",
    copyFailed: "Copy failed. Select the command and copy it manually.",
    setupTitle: "Global setup is optional.",
    setupBody: "Core installation does not write ~/.codex/AGENTS.md, enable Hooks, install Rules, or install Rootloom Memory.",
    readSetup: "Read setup and rollback",
    limitsTitle: "Useful because it stays narrow.",
    limitsBody: "Rootloom owns the execution and review boundary. Existing engineering tools keep doing their own jobs.",
    isTitle: "Rootloom is",
    isOne: "A native Codex plugin plus Agent Plugins preview",
    isTwo: "Single-agent by default",
    isThree: "Python-standard-library-only at runtime",
    isFour: "Lightweight for ordinary changes",
    isNotTitle: "Rootloom is not",
    isNotOne: "A specification framework or test runner",
    isNotTwo: "A secret scanner or sandbox",
    isNotThree: "Proof that a change is correct or secure",
    isNotFour: "Feature parity across every coding-agent client",
    docAgentPlugins: "Agent Plugins preview",
    docArchitecture: "Architecture",
    docMaturity: "Maturity and guarantees",
    docTroubleshooting: "Troubleshooting",
    docReleases: "Releases",
    footerLine: "Codex-native engineering with a bounded portable preview.",
    githubRepository: "GitHub repository",
    license: "MIT License",
  },
  zh: {
    pageTitle: "Rootloom — 让每一次代码修改都说得清",
    pageDescription: "Rootloom 是一个 OpenAI Codex 原生工程插件，并提供可移植 Change、Review 与 Project Guidance 的 Agent Plugins 预览。",
    skip: "跳到主要内容",
    menu: "菜单",
    openMenu: "打开导航",
    closeMenu: "关闭导航",
    navWhy: "为什么需要",
    navHow: "如何工作",
    navWorkflows: "工作流",
    navDocs: "文档",
    github: "GitHub",
    heroTitle: "让\u2060每\u2060一\u2060次代\u2060码\u2060修\u2060改，都\u2060说\u2060得\u2060清。",
    heroBody: "Rootloom 为代码 Agent 建立一条清晰路径：从仓库证据出发，做聚焦的修改，并给出可以复核的验证结果。",
    installCta: "安装 Rootloom",
    viewGithub: "查看 GitHub",
    copyBoth: "复制两条命令",
    heroNote: "这些命令安装 Codex 原生插件；独立的 Agent Plugins 预览提供可移植 Change、Review 与 Project Guidance。",
    heroAlt: "一只黑猫操作织布机，把混乱的风险、缺陷和上下文织成带勾的结果",
    problemTitle: "多数编码失败，发生在 Diff 之前。",
    problemBody: "Agent 可能在错误边界写出看似合理的代码，运行一条方便的测试，然后报告超出证据范围的确定性。Rootloom 改变的是这段过程。",
    failureOneTitle: "给现象打补丁",
    failureOneBody: "报错处多了一个 Guard，真正拥有这段行为的组件仍然有问题。",
    failureTwoTitle: "只测试顺利路径",
    failureTwoBody: "重连通过了，取消与正常断开却在不知不觉中发生偏移。",
    failureThreeTitle: "笼统报告结果",
    failureThreeBody: "建议运行的检查和真正执行的检查，被写进了同一句话。",
    middleTitle: "Rootloom 让中间过程变得可见。",
    middleBody: "补丁只是一次工程决策中的一步，不是全部。",
    flowAria: "Rootloom 从请求到验证报告的工程流程",
    flowRequest: "任务请求",
    flowEvidence: "仓库证据",
    flowScope: "风险与范围",
    flowOwner: "行为归属边界",
    flowChange: "聚焦修改",
    flowReport: "验证报告",
    workflowTitle: "从请求到证据，每一步都有明确归属。",
    workflowBody: "普通任务仍走仓库原有的编辑和测试路径。Rootloom 补上的是这条路径周围的工程纪律。",
    stepOneTitle: "读取项目",
    stepOneBody: "修改前检查源码、测试、项目规则和已有工作。",
    stepTwoTitle: "判断风险与范围",
    stepTwoBody: "让工作流匹配影响范围，并说明什么不应该改变。",
    stepThreeTitle: "找到行为归属",
    stepThreeBody: "处理缺陷时，从触发条件追到真正拥有不变量的边界。",
    stepFourTitle: "完成聚焦修改",
    stepFourBody: "沿用仓库架构，并保护与当前任务无关的工作。",
    stepFiveTitle: "验证并报告",
    stepFiveBody: "检查主路径、不变量和相邻路径，并列出真正执行的命令。",
    workflowAlt: "Rootloom 织布机示意图：风险、缺陷和上下文经过证据、契约与测试，得到已验证结果",
    workflowCaption: "这台织布机就是产品模型：混乱输入经过证据、范围和测试，成为可以审查的结果。",
    workflowsTitle: "一个 Core，四个公共入口。",
    workflowsBody: "Change 在内部路由风险与证据模式，用户按意图选择，不必理解治理机制。",
    choiceChangeTitle: "日常修改",
    choiceChangeBody: "实现、修复或重构普通代码，并进行范围明确的验证。",
    choiceReviewTitle: "只做审查",
    choiceReviewBody: "检查 Diff、PR、Migration 或设计，不修改文件。",
    choiceRiskTitle: "项目指导",
    choiceRiskBody: "创建、刷新、精炼或检查简洁的 AGENTS.md 指导。",
    choiceSetupTitle: "设置",
    choiceSetupBody: "安装、升级、检查或回滚可选全局指导与 Autonomy Rules。",
    optionalPrefix: "需要治理式修改或机器可读证据包？",
    optionalSuffix: "只在明确需要时加载对应模式。",
    allSkills: "查看四个 Skills",
    evidenceTitle: "完成报告应当说明真正发生了什么。",
    evidenceBody: "Rootloom 把计划、命令结果、仓库状态和人工判断分别记录，不混为一谈。",
    evidenceOneTitle: "计划始终标记为计划。",
    evidenceOneBody: "自动生成的验证命令，在真正运行前只是一条建议。",
    evidenceTwoTitle: "命令结束后再次检查状态。",
    evidenceTwoBody: "如果仓库或采集证据已经改变，退出码 0 仍然不足以完成任务。",
    evidenceThreeTitle: "证据支撑判断。",
    evidenceThreeBody: "它让审查可以复核，但不会证明代码一定正确或安全。",
    caseBody: "Rootloom 的一条真实回归虽然命令通过，却因为仓库状态随后改变而没有通过审查。",
    readCase: "阅读真实案例",
    installTitle: "从 Codex 原生插件开始。",
    installBody: "以下命令安装完整 Codex 体验；兼容 Agent Plugins 的客户端可以从 portable/rootloom 加载三 Skill 预览，具体见下方预览指南。",
    installOneTitle: "添加 Marketplace",
    installTwoTitle: "安装 Rootloom",
    installThreeTitle: "新建一个任务",
    promptExample: "修复重连竞态，并验证重连、正常断开和取消路径。",
    copy: "复制",
    copied: "已复制",
    copiedStatus: "命令已复制到剪贴板。",
    copyFailed: "复制失败，请选中命令后手动复制。",
    setupTitle: "全局设置是可选的。",
    setupBody: "安装 Core 不会写入 ~/.codex/AGENTS.md、启用 Hook、安装 Rules 或安装 Rootloom Memory。",
    readSetup: "查看安装与回滚",
    limitsTitle: "价值来自清楚的边界。",
    limitsBody: "Rootloom 负责执行与审查的交界处，现有工程工具继续完成各自的工作。",
    isTitle: "Rootloom 是",
    isOne: "Codex 原生插件与 Agent Plugins 预览",
    isTwo: "默认单代理运行",
    isThree: "运行时只依赖 Python 标准库",
    isFour: "适合普通修改的轻量工作流",
    isNotTitle: "Rootloom 不是",
    isNotOne: "需求规格框架或测试 Runner",
    isNotTwo: "Secret Scanner 或沙箱",
    isNotThree: "修改正确或安全的证明",
    isNotFour: "所有 Coding Agent 客户端中的功能等价",
    docAgentPlugins: "Agent Plugins 预览",
    docArchitecture: "架构",
    docMaturity: "成熟度与保证",
    docTroubleshooting: "排障",
    docReleases: "版本发布",
    footerLine: "Codex 原生工程工作流，并提供边界明确的可移植预览。",
    githubRepository: "GitHub 仓库",
    license: "MIT 许可证",
  },
};

const commands = document.querySelectorAll("[data-copy]");
const copyStatus = document.querySelector("[data-copy-status]");
const languageToggle = document.querySelector("[data-language-toggle]");
const menuToggle = document.querySelector("[data-menu-toggle]");
const siteNav = document.querySelector("[data-site-nav]");
let currentLanguage = "en";
let copyStatusTimer;

function getPreferredLanguage() {
  const saved = localStorage.getItem("rootloom-language");
  if (saved === "en" || saved === "zh") return saved;
  return navigator.language.toLowerCase().startsWith("zh") ? "zh" : "en";
}

function setLocalizedText(language) {
  const dictionary = messages[language];

  document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  document.documentElement.dataset.lang = language;
  document.title = dictionary.pageTitle;

  const description = document.querySelector('meta[name="description"]');
  const ogTitle = document.querySelector('meta[property="og:title"]');
  const ogDescription = document.querySelector('meta[property="og:description"]');
  if (description) description.content = dictionary.pageDescription;
  if (ogTitle) ogTitle.content = dictionary.pageTitle;
  if (ogDescription) ogDescription.content = dictionary.pageDescription;

  document.querySelectorAll("[data-i18n]").forEach((element) => {
    const key = element.dataset.i18n;
    if (dictionary[key]) element.textContent = dictionary[key];
  });

  document.querySelectorAll("[data-i18n-aria]").forEach((element) => {
    const key = element.dataset.i18nAria;
    if (dictionary[key]) element.setAttribute("aria-label", dictionary[key]);
  });

  document.querySelectorAll("[data-i18n-alt]").forEach((element) => {
    const key = element.dataset.i18nAlt;
    if (dictionary[key]) element.setAttribute("alt", dictionary[key]);
  });

  const workflowImage = document.querySelector("[data-workflow-image]");
  if (workflowImage) workflowImage.src = workflowImage.dataset[`image${language === "zh" ? "Zh" : "En"}`];

  const caseLink = document.querySelector("[data-case-link]");
  if (caseLink) caseLink.href = caseLink.dataset[`case${language === "zh" ? "Zh" : "En"}`];

  const setupLink = document.querySelector("[data-setup-link]");
  if (setupLink) setupLink.href = setupLink.dataset[`setup${language === "zh" ? "Zh" : "En"}`];

  document.querySelectorAll("[data-doc]").forEach((link) => {
    const slug = link.dataset.doc;
    const suffix = language === "zh" ? ".zh-CN.md" : ".md";
    link.href = `https://github.com/liyanqing90/rootloom/blob/main/docs/${slug}${suffix}`;
  });

  languageToggle.textContent = language === "zh" ? "EN" : "中文";
  languageToggle.lang = language === "zh" ? "en" : "zh-CN";
  languageToggle.setAttribute("aria-label", language === "zh" ? "Switch to English" : "切换到中文");

  currentLanguage = language;
  localStorage.setItem("rootloom-language", language);
}

function setMenu(open) {
  menuToggle.setAttribute("aria-expanded", String(open));
  menuToggle.setAttribute("aria-label", messages[currentLanguage][open ? "closeMenu" : "openMenu"]);
  siteNav.classList.toggle("is-open", open);
  document.body.classList.toggle("menu-open", open);
}

async function writeClipboard(value) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(value);
    return;
  }

  const textArea = document.createElement("textarea");
  textArea.value = value;
  textArea.setAttribute("readonly", "");
  textArea.style.position = "fixed";
  textArea.style.opacity = "0";
  document.body.appendChild(textArea);
  textArea.select();
  const copied = document.execCommand("copy");
  textArea.remove();
  if (!copied) throw new Error("Clipboard copy was rejected");
}

function showCopyStatus(message) {
  window.clearTimeout(copyStatusTimer);
  copyStatus.textContent = message;
  copyStatus.classList.add("is-visible");
  copyStatusTimer = window.setTimeout(() => copyStatus.classList.remove("is-visible"), 3000);
}

commands.forEach((button) => {
  button.addEventListener("click", async () => {
    const key = button.dataset.copy;
    const originalKey = key === "install" ? "copyBoth" : "copy";
    try {
      await writeClipboard(copyValues[key]);
      button.textContent = messages[currentLanguage].copied;
      button.classList.add("is-copied");
      showCopyStatus(messages[currentLanguage].copiedStatus);
      window.setTimeout(() => {
        button.textContent = messages[currentLanguage][originalKey];
        button.classList.remove("is-copied");
      }, 3000);
    } catch (error) {
      showCopyStatus(messages[currentLanguage].copyFailed);
    }
  });
});

languageToggle.addEventListener("click", () => {
  setLocalizedText(currentLanguage === "en" ? "zh" : "en");
  setMenu(false);
});

menuToggle.addEventListener("click", () => {
  setMenu(menuToggle.getAttribute("aria-expanded") !== "true");
});

siteNav.querySelectorAll("a").forEach((link) => {
  link.addEventListener("click", () => setMenu(false));
});

window.addEventListener("resize", () => {
  if (window.innerWidth > 820) setMenu(false);
});

setLocalizedText(getPreferredLanguage());
