import React, { useState, useEffect, useRef } from "react";
import {
  LayoutDashboard,
  Megaphone,
  Users,
  ShoppingCart,
  FileText,
  ShieldBan,
  Settings,
  Send,
  Plus,
  RefreshCw,
  CheckCircle2,
  Lock,
  LogOut,
  IndianRupee,
  MessageSquare,
  Search,
  Filter,
  ArrowUpDown,
  Trash2,
  Edit2,
  UserPlus,
  Key,
  AlertTriangle,
  PlayCircle,
  BookOpen,
  Sliders,
  ToggleLeft,
  ToggleRight,
  ShieldCheck,
  ShieldAlert,
  Tag,
  Eye,
  EyeOff,
  Ticket,
  Upload,
  Calendar,
  Gift,
  ChevronLeft,
  ChevronRight,
  Clock,
  Star,
  Package,
  CloudRain,
  Activity,
  Zap,
  Radio,
  BellRing,
  Mail,
  KeyRound,
  Smartphone,
  Check,
  CheckCheck,
  Sparkles,
  PhoneCall,
  GitBranch,
  Play,
  BarChart3,
  TrendingUp,
  MousePointerClick,
  ArrowRight,
  Volume2,
  VolumeX
} from "lucide-react";
import axios, { getApiBaseUrl, renderProductionUrl as RENDER_PROD_URL, setApiBaseUrl, cachedGet, invalidateCache } from "./api";
import FlowchartCanvas from "./components/FlowchartCanvas";
import DashboardPage from "./pages/DashboardPage";
import AutomationsPage from "./pages/AutomationsPage";
import SettingsPage from "./pages/SettingsPage";
import TemplatesPage from "./pages/TemplatesPage";
import CampaignsPage from "./pages/CampaignsPage";
import AnalyticsPage from "./pages/AnalyticsPage";
import ContactsPage from "./pages/ContactsPage";
import MessageLogsPage from "./pages/MessageLogsPage";
import OptOutPage from "./pages/OptOutPage";
import LiveChatPage from "./pages/LiveChatPage";
import PerformanceNocPage from "./pages/PerformanceNocPage";

const INITIAL_API_BASE_URL = getApiBaseUrl();
setApiBaseUrl(INITIAL_API_BASE_URL);

import {
  formatToIST,
  formatToISTTime,
  formatToISTDate,
  getTodayISTDateString,
  formatScheduleDisplay
} from "./utils/dateUtils";
import { playIncomingMessageSound as playMessageSoundHelper } from "./utils/audio";

import LoginView from "./components/auth/LoginView";
import CampaignModal from "./components/modals/CampaignModal";
import SecurityActionModal from "./components/modals/SecurityActionModal";
import ContactModal from "./components/modals/ContactModal";
import CsvImportModal from "./components/modals/CsvImportModal";
import TemplateModal from "./components/modals/TemplateModal";
import TemplateMappingModal from "./components/modals/TemplateMappingModal";
import NewJourneyModal from "./components/modals/NewJourneyModal";
import JourneySessionsModal from "./components/modals/JourneySessionsModal";
import AutomationAnalyticsPage from "./pages/AutomationAnalyticsPage";
import { AddUserModal, AdminPasswordModal, RoleInfoModal } from "./components/modals/UserManagementModals";
import { TwoFactorSetupModal, TwoFactorDisableModal } from "./components/modals/TwoFactorModals";

// Re-export for external modules if any
export { formatToIST, formatToISTTime, formatToISTDate, getTodayISTDateString, formatScheduleDisplay };
export default function App() {
  const [serverUrl, setServerUrl] = useState(INITIAL_API_BASE_URL);
  const [showServerModal, setShowServerModal] = useState(false);
  const [serverInput, setServerInput] = useState(INITIAL_API_BASE_URL);
  const [serverTestStatus, setServerTestStatus] = useState(null);

  const [token, setToken] = useState(localStorage.getItem("token") || "");
  const [username, setUsername] = useState(localStorage.getItem("username") || "");
  const [authMode, setAuthMode] = useState("login"); // "login" or "register"
  const [loginForm, setLoginForm] = useState({ username: "", password: "" });
  const [registerForm, setRegisterForm] = useState({ username: "", email: "", password: "" });
  const [loginError, setLoginError] = useState("");
  const [authSuccess, setAuthSuccess] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [registrationStatus, setRegistrationStatus] = useState({
    current_users: 1,
    max_users: 5,
    can_register: true
  });

  // 2FA Authentication Challenge & Setup States
  const [twoFactorRequired, setTwoFactorRequired] = useState(false);
  const [twoFactorTempToken, setTwoFactorTempToken] = useState("");
  const [twoFactorCode, setTwoFactorCode] = useState("");
  const [twoFactorMethod, setTwoFactorMethod] = useState("totp"); // "totp" or "email"
  const [twoFactorEmailSent, setTwoFactorEmailSent] = useState(false);
  const [twoFactorEmailPreview, setTwoFactorEmailPreview] = useState("");
  const [twoFactorLoading, setTwoFactorLoading] = useState(false);

  // 2FA Configuration in Settings States
  const [is2faModalOpen, setIs2faModalOpen] = useState(false);
  const [twoFactorSetupData, setTwoFactorSetupData] = useState(null);
  const [setupVerifyCode, setSetupVerifyCode] = useState("");
  const [setupVerifyLoading, setSetupVerifyLoading] = useState(false);
  const [setupVerifyError, setSetupVerifyError] = useState("");
  const [isDisable2faModalOpen, setIsDisable2faModalOpen] = useState(false);
  const [disablePassword, setDisablePassword] = useState("");
  const [disableLoading, setDisableLoading] = useState(false);
  const [currentUserProfile, setCurrentUserProfile] = useState(null);

  const getInitialTab = () => {
    const hash = window.location.hash.replace("#", "");
    if (hash && ["dashboard", "chat", "automations", "campaigns", "analytics", "performance", "templates", "contacts", "logs", "opt_out", "settings"].includes(hash)) {
      return hash;
    }
    return localStorage.getItem("activeTab") || "dashboard";
  };

  const [activeTab, setActiveTab] = useState(getInitialTab);

  const handleTabChange = (tabId) => {
    setActiveTab(tabId);
    setSearchTerm("");
    localStorage.setItem("activeTab", tabId);
    window.location.hash = tabId;
  };

  // Mobile Device Integrations (Capacitor StatusBar & SplashScreen)
  useEffect(() => {
    const initMobileDevice = async () => {
      try {
        const { StatusBar, Style } = await import("@capacitor/status-bar");
        await StatusBar.setStyle({ style: Style.Dark }).catch(() => {});
        await StatusBar.setBackgroundColor({ color: "#064e3b" }).catch(() => {});
      } catch (e) {}

      try {
        const { SplashScreen } = await import("@capacitor/splash-screen");
        await SplashScreen.hide().catch(() => {});
      } catch (e) {}
    };
    initMobileDevice();
  }, []);

  // Android Hardware Back Button Handling
  useEffect(() => {
    let unlisten = null;
    const registerBackButton = async () => {
      try {
        const { App: CapApp } = await import("@capacitor/app");
        const listener = await CapApp.addListener("backButton", ({ canGoBack }) => {
          if (activeTab !== "dashboard") {
            setActiveTab("dashboard");
          } else if (canGoBack) {
            window.history.back();
          } else {
            CapApp.exitApp();
          }
        });
        unlisten = () => listener.remove();
      } catch (e) {}
    };
    registerBackButton();
    return () => {
      if (unlisten) unlisten();
    };
  }, [activeTab]);
  const [campaigns, setCampaigns] = useState([]);
  const [contacts, setContacts] = useState([]);
  const [discountCodes, setDiscountCodes] = useState([]);
  const [cartEvents, setCartEvents] = useState([]);
  const [messageLogs, setMessageLogs] = useState([]);
  const [optOuts, setOptOuts] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [externalDataSources, setExternalDataSources] = useState([]);
  const [automationRules, setAutomationRules] = useState([]);
  const [workflowFlows, setWorkflowFlows] = useState([]);
  const [editingWorkflow, setEditingWorkflow] = useState(null);
  const [systemSettings, setSystemSettings] = useState({});
  const [systemUsers, setSystemUsers] = useState([]);
  const [templateFilterLang, setTemplateFilterLang] = useState("ALL");
  const [templatePage, setTemplatePage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [actionSuccessMsg, setActionSuccessMsg] = useState("");
  const [testEmailLoading, setTestEmailLoading] = useState(false);
  const [testEmailFeedback, setTestEmailFeedback] = useState(null);

  // Two-Way WhatsApp Live Chat States
  const [chatConversations, setChatConversations] = useState([]);
  const [selectedChatPhone, setSelectedChatPhone] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatReplyText, setChatReplyText] = useState("");
  const [chatSending, setChatSending] = useState(false);
  const [chatFilterUnreadOnly, setChatFilterUnreadOnly] = useState(false);
  const [chatListCollapsed, setChatListCollapsed] = useState(() => {
    return localStorage.getItem("chatListCollapsed") === "true";
  });
  const [chatSoundEnabled, setChatSoundEnabled] = useState(true);
  const lastProcessedMessageIdRef = useRef(null);
  const isInitialChatLoadRef = useRef(true);
  const lastKnownIncomingSignatureRef = useRef(null);
  const isInitialConversationsLoadRef = useRef(true);


  // Pleasant Web Audio Chime for Live Chat Incoming Messages (Zero external MP3 dependencies)
  const playIncomingMessageSound = () => {
    playMessageSoundHelper(chatSoundEnabled);
  };

  // WhatsApp Delivery & Engagement Analytics States
  const [analyticsData, setAnalyticsData] = useState(null);
  const [analyticsTimeRange, setAnalyticsTimeRange] = useState("30d");
  const [analyticsLoading, setAnalyticsLoading] = useState(false);

  // Layout UI States
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Search filter for lists
  const [searchTerm, setSearchTerm] = useState("");

  // Contacts Pagination & Filtering State
  const [contactsPage, setContactsPage] = useState(1);
  const [contactsPerPage, setContactsPerPage] = useState(50);
  const [contactSortField, setContactSortField] = useState("id");
  const [contactSortOrder, setContactSortOrder] = useState("desc");
  const [contactFilterCity, setContactFilterCity] = useState("ALL");
  const [contactFilterTag, setContactFilterTag] = useState("ALL");
  const [contactFilterVip, setContactFilterVip] = useState("ALL");
  const [contactFilterOrders, setContactFilterOrders] = useState("ALL");

  // Single Contact Add / Edit Modal State
  const [isContactModalOpen, setIsContactModalOpen] = useState(false);
  const [editingContactId, setEditingContactId] = useState(null);
  const [contactForm, setContactForm] = useState({
    phone: "",
    name: "",
    email: "",
    city: "",
    tags: "",
    total_orders: 0,
    last_order_date: ""
  });
  const [contactSaving, setContactSaving] = useState(false);

  // New Campaign Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newCampaign, setNewCampaign] = useState({
    title: "",
    template_name: "",
    language: "en",
    target_filter: "ALL",
    message_type: "marketing",
    per_day_limit: "",
    scheduled_for: ""
  });

  const handleOpenCampaignModal = () => {
    const approvedTmpl = templates.find((t) => t.status === "APPROVED") || templates[0];
    setNewCampaign({
      title: "",
      template_name: approvedTmpl ? approvedTmpl.template_name : "",
      language: approvedTmpl ? (approvedTmpl.language || "en") : "en",
      target_filter: "ALL",
      message_type: "marketing",
      per_day_limit: "",
      scheduled_for: ""
    });
    setIsModalOpen(true);
  };

  // Step-Up Security & 2FA Modal States (for Campaign Launch & Automation Release)
  const [securityActionModal, setSecurityActionModal] = useState({
    isOpen: false,
    actionType: null, // "CAMPAIGN" or "AUTOMATION_APPROVAL"
    title: "",
    recipientCount: 0,
    payloadData: null,
    password: "",
    twoFactorCode: "",
    error: "",
    loading: false
  });

  // CSV Import Modal State
  const [isCsvModalOpen, setIsCsvModalOpen] = useState(false);
  const [csvFile, setCsvFile] = useState(null);
  const [csvImporting, setCsvImporting] = useState(false);

  // New Discount Code Modal State
  const [isDiscountModalOpen, setIsDiscountModalOpen] = useState(false);
  const [newDiscountCode, setNewDiscountCode] = useState({
    code: "",
    discount_type: "PERCENT",
    discount_value: 10,
    min_order_value: 0,
    max_uses: 1000,
    expires_at: ""
  });

  // New Template Modal State
  const [isTemplateModalOpen, setIsTemplateModalOpen] = useState(false);
  const [newTemplate, setNewTemplate] = useState({
    template_name: "",
    category: "MARKETING",
    language: "en",
    header_text: "",
    body_text: "",
    footer_text: "JWL",
    variable_mappings: {}
  });
  // Template Mapping Editor State (for existing templates)
  const [editMappingTemplate, setEditMappingTemplate] = useState(null); // template object being edited
  const [editMappings, setEditMappings] = useState({});                  // working copy of mappings

  // New Journey Flow Modal State
  const [isNewJourneyModalOpen, setIsNewJourneyModalOpen] = useState(false);
  const [newJourneyForm, setNewJourneyForm] = useState({
    name: "",
    trigger_type: "ABANDONED_CART",
    min_cart_value: 0,
    inactive_days: 30,
    weather_condition: "RAINY",
    city: "Ahmedabad",
    welcome_coupon: "WELCOME10",
    product_name: "Solitaire Special"
  });

  const handleOpenNewJourneyModal = () => {
    setNewJourneyForm({
      name: "",
      trigger_type: "ABANDONED_CART",
      min_cart_value: 0,
      inactive_days: 30,
      weather_condition: "RAINY",
      city: "Ahmedabad",
      welcome_coupon: "WELCOME10",
      product_name: "Solitaire Special"
    });
    setIsNewJourneyModalOpen(true);
  };

  const handleConfirmCreateJourney = (e) => {
    e?.preventDefault();
    const triggerLabels = {
      ABANDONED_CART: "Abandoned Cart",
      INACTIVE_WINBACK: "Customer Inactive Winback",
      WEATHER_TRIGGER: "Weather Trigger",
      NEW_CUSTOMER_WELCOME: "New Customer Welcome",
      BACK_IN_STOCK: "Back In Stock Alert",
      FESTIVAL_OFFER: "Festival / Promotional Event",
      ORDER_COMPLETED: "Post-Purchase Order Completed",
      CONTACT_TAGGED: "Customer Tagged / VIP"
    };
    const tType = newJourneyForm.trigger_type || "ABANDONED_CART";
    const tLabel = triggerLabels[tType] || "Trigger";
    const defaultName = newJourneyForm.name.trim() || `${tLabel} Flow`;
    const minCartVal = Number(newJourneyForm.min_cart_value) || 0;
    const inactiveDaysVal = Number(newJourneyForm.inactive_days) || 30;

    let triggerConfig = {};
    let nodeData = { trigger_type: tType };

    if (tType === "ABANDONED_CART") {
      triggerConfig = { min_cart_value: minCartVal };
      nodeData.min_cart_value = minCartVal;
      nodeData.description = minCartVal > 0 ? `Min Cart: ≥ ₹${minCartVal}` : "All Cart Events";
    } else if (tType === "INACTIVE_WINBACK") {
      triggerConfig = { inactive_days: inactiveDaysVal };
      nodeData.inactive_days = inactiveDaysVal;
      nodeData.description = `Inactive ≥ ${inactiveDaysVal} Days`;
    } else if (tType === "WEATHER_TRIGGER") {
      const wCond = newJourneyForm.weather_condition || "RAINY";
      const wCity = newJourneyForm.city || "Ahmedabad";
      triggerConfig = { weather_condition: wCond, city: wCity };
      nodeData.weather_condition = wCond;
      nodeData.city = wCity;
      nodeData.description = `${wCond} in ${wCity}`;
    } else if (tType === "NEW_CUSTOMER_WELCOME") {
      const coupon = (newJourneyForm.welcome_coupon || "WELCOME10").toUpperCase();
      triggerConfig = { welcome_coupon: coupon };
      nodeData.welcome_coupon = coupon;
      nodeData.description = `New Customer • Code: ${coupon}`;
    } else if (tType === "BACK_IN_STOCK") {
      const pName = newJourneyForm.product_name || "Solitaire Special";
      triggerConfig = { product_name: pName };
      nodeData.product_name = pName;
      nodeData.description = `Restocked: ${pName}`;
    } else {
      nodeData.description = "Starting Trigger";
    }

    let initialNodes = [
      {
        id: "node_1",
        type: "trigger",
        label: `${tLabel} Trigger`,
        position: { x: 280, y: 40 },
        data: nodeData
      }
    ];
    let initialEdges = [];

    if (tType === "NEW_CUSTOMER_WELCOME") {
      const coupon = (newJourneyForm.welcome_coupon || "WELCOME10").toUpperCase();
      initialNodes = [
        {
          id: "node_1",
          type: "trigger",
          label: "New Customer Signup",
          position: { x: 280, y: 40 },
          data: {
            ...nodeData,
            description: "Triggers on website registration"
          }
        },
        {
          id: "node_2",
          type: "whatsapp_message",
          label: "Send Double Opt-In Invite",
          position: { x: 280, y: 160 },
          data: {
            template_name: "welcome_greeting",
            description: "Requests affirmative WhatsApp marketing consent"
          }
        },
        {
          id: "node_3",
          type: "delay",
          label: "Wait 2 Hours for Reply",
          position: { x: 280, y: 280 },
          data: {
            delay_minutes: 120,
            display_value: 2,
            unit: "hours",
            description: "Wait up to 2 hours for reply"
          }
        },
        {
          id: "node_4",
          type: "condition",
          label: "Did Customer Confirm Opt-In?",
          position: { x: 280, y: 400 },
          data: {
            condition_type: "DOUBLE_OPTIN_CONFIRMED",
            description: "Checks affirmative consent record"
          }
        },
        {
          id: "node_5",
          type: "tag",
          label: "Tag: Double Opt-In Confirmed",
          position: { x: 120, y: 520 },
          data: {
            tag_name: "Double Opt-In Confirmed",
            description: "Tags contact as consented"
          }
        },
        {
          id: "node_6",
          type: "whatsapp_message",
          label: `Send Welcome Gift (${coupon})`,
          position: { x: 120, y: 640 },
          data: {
            template_name: "cart_recovery_v1",
            coupon_code: coupon,
            description: `Delivers ${coupon} discount code`
          }
        },
        {
          id: "node_7",
          type: "tag",
          label: "Tag: Pending Consent",
          position: { x: 440, y: 520 },
          data: {
            tag_name: "Unconfirmed Consent",
            description: "Tags contact without consent"
          }
        }
      ];
      initialEdges = [
        { id: "e-1-2", source: "node_1", target: "node_2" },
        { id: "e-2-3", source: "node_2", target: "node_3" },
        { id: "e-3-4", source: "node_3", target: "node_4" },
        { id: "e-4-5", source: "node_4", target: "node_5", sourceHandle: "yes" },
        { id: "e-5-6", source: "node_5", target: "node_6" },
        { id: "e-4-7", source: "node_4", target: "node_7", sourceHandle: "no" }
      ];
    }

    const newWf = {
      name: defaultName,
      description: `Multi-step automated flowchart journey starting with ${tLabel}`,
      trigger_type: tType,
      trigger_config: triggerConfig,
      is_active: true,
      nodes: initialNodes,
      edges: initialEdges,
      stats: { entered: 0, completed: 0, goals_converted: 0, revenue_recovered: 0 }
    };

    setIsNewJourneyModalOpen(false);
    setEditingWorkflow(newWf);
  };


  // Journey Enrolled Contacts / Sessions Modal State
  const [journeySessionsModal, setJourneySessionsModal] = useState({
    isOpen: false,
    flow: null,
    sessions: [],
    loading: false,
    search: "",
    statusFilter: "ALL"
  });

  // Full-screen analytics page state
  const [analyticsPage, setAnalyticsPage] = useState({ open: false, flow: null, sessions: [], loading: false });

  const handleOpenJourneySessions = async (flow) => {
    setJourneySessionsModal({
      isOpen: true,
      flow,
      sessions: [],
      loading: true,
      search: "",
      statusFilter: "ALL"
    });
    try {
      const res = await axios.get(`/api/workflows/${flow.id}/sessions`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setJourneySessionsModal((prev) => ({
        ...prev,
        sessions: res.data || [],
        loading: false
      }));
    } catch (err) {
      console.error("Failed to fetch journey sessions:", err);
      setJourneySessionsModal((prev) => ({
        ...prev,
        loading: false
      }));
    }
  };

  const handleOpenAnalyticsPage = async (flow, silent = false) => {
    if (!silent) {
      setAnalyticsPage(prev => ({ ...prev, open: true, flow, loading: true }));
    }
    try {
      const res = await axios.get(`/api/workflows/${flow.id}/sessions`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setAnalyticsPage(prev => ({ ...prev, open: true, flow, sessions: res.data || [], loading: false }));
    } catch (err) {
      console.error("Failed to fetch analytics sessions:", err);
      setAnalyticsPage(prev => ({ ...prev, loading: false }));
    }
  };

  // Add User from Settings Modal State
  const [isAddUserModalOpen, setIsAddUserModalOpen] = useState(false);
  const [newUserForm, setNewUserForm] = useState({ username: "", email: "", password: "", role: "agent" });
  const [addUserLoading, setAddUserLoading] = useState(false);
  const [addUserError, setAddUserError] = useState("");
  const [userRoleUpdatingId, setUserRoleUpdatingId] = useState(null);

  const handleCreateUserFromSettings = async (e) => {
    e.preventDefault();
    if (!token) return;
    setAddUserLoading(true);
    setAddUserError("");
    try {
      await axios.post("/api/users", newUserForm, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setActionSuccessMsg(`Team user "${newUserForm.username}"registered successfully!`);
      setIsAddUserModalOpen(false);
      setNewUserForm({ username: "", email: "", password: "", role: "agent" });
      fetchData(true);
      setTimeout(() => setActionSuccessMsg(""), 6000);
    } catch (err) {
      setAddUserError(err.response?.data?.detail || err.message || "Failed to create user");
    } finally {
      setAddUserLoading(false);
    }
  };

  const handleUpdateUserRole = async (targetUser, newRole) => {
    const actionLabel = newRole === "admin" ? "promote" : "demote";
    const titleLabel = newRole === "admin" ? "Admin (Full Access)" : "Team Member";
    if (!window.confirm(`Are you sure you want to ${actionLabel} ${targetUser.username} to ${titleLabel}?`)) {
      return;
    }
    setUserRoleUpdatingId(targetUser.id);
    try {
      await axios.put(`/api/users/${targetUser.id}/role`, { role: newRole }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSystemUsers((prev) =>
        prev.map((u) => (u.id === targetUser.id ? { ...u, role: newRole } : u))
      );
      setActionSuccessMsg(` ${targetUser.username} has been updated to ${titleLabel}!`);
      fetchData(true);
      setTimeout(() => setActionSuccessMsg(""), 5000);
    } catch (err) {
      alert("Failed to update user role: " + (err.response?.data?.detail || err.message));
      fetchData(true);
    } finally {
      setUserRoleUpdatingId(null);
    }
  };

  // Admin Password Reset Modal State
  const [adminPasswordModal, setAdminPasswordModal] = useState({
    isOpen: false,
    user: null,
    newPassword: "",
    confirmPassword: "",
    loading: false,
    error: ""
  });

  const handleAdminResetPassword = async (e) => {
    e.preventDefault();
    if (!adminPasswordModal.user) return;
    if (adminPasswordModal.newPassword.length < 6) {
      setAdminPasswordModal((prev) => ({ ...prev, error: "Password must be at least 6 characters long." }));
      return;
    }
    if (adminPasswordModal.newPassword !== adminPasswordModal.confirmPassword) {
      setAdminPasswordModal((prev) => ({ ...prev, error: "Passwords do not match." }));
      return;
    }
    setAdminPasswordModal((prev) => ({ ...prev, loading: true, error: "" }));
    try {
      await axios.put(`/api/users/${adminPasswordModal.user.id}/password`, {
        new_password: adminPasswordModal.newPassword
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setActionSuccessMsg(`Password for ${adminPasswordModal.user.username} updated successfully!`);
      setAdminPasswordModal({ isOpen: false, user: null, newPassword: "", confirmPassword: "", loading: false, error: "" });
      setTimeout(() => setActionSuccessMsg(""), 5000);
    } catch (err) {
      setAdminPasswordModal((prev) => ({
        ...prev,
        loading: false,
        error: err.response?.data?.detail || err.message || "Failed to update password"
      }));
    }
  };

  // Admin 2FA Toggle Handler
  const [admin2faUpdatingId, setAdmin2faUpdatingId] = useState(null);
  const handleAdminToggle2FA = async (targetUser, enable) => {
    const action = enable ? "enable" : "disable";
    const msg = enable
      ? `Are you sure you want to enable 2FA requirement for ${targetUser.username}?`
      : `Are you sure you want to disable 2FA for ${targetUser.username}? (This allows them to log in if they lost their Authenticator app).`;
    if (!window.confirm(msg)) return;
    setAdmin2faUpdatingId(targetUser.id);
    try {
      await axios.put(`/api/users/${targetUser.id}/2fa`, { enabled: enable }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSystemUsers((prev) =>
        prev.map((u) => (u.id === targetUser.id ? { ...u, is_2fa_enabled: enable } : u))
      );
      setActionSuccessMsg(`2FA has been ${action}d for ${targetUser.username}!`);
      fetchData(true);
      setTimeout(() => setActionSuccessMsg(""), 5000);
    } catch (err) {
      alert(`Failed to ${action} 2FA: ` + (err.response?.data?.detail || err.message));
      fetchData(true);
    } finally {
      setAdmin2faUpdatingId(null);
    }
  };

  // User Deletion Handler (Admin only; cannot delete other Admins or self)
  const [userDeletingId, setUserDeletingId] = useState(null);
  const [isRoleInfoModalOpen, setIsRoleInfoModalOpen] = useState(false);

  const handleDeleteUser = async (targetUser) => {
    if (targetUser.role === "admin") {
      alert("Admins cannot be deleted. If you wish to delete this account, demote it to a Team Member first.");
      return;
    }
    if (targetUser.username === username) {
      alert("You cannot delete your own account.");
      return;
    }
    if (!window.confirm(`Are you sure you want to permanently delete user "${targetUser.username}" (${targetUser.email})? This action cannot be undone.`)) {
      return;
    }
    setUserDeletingId(targetUser.id);
    try {
      await axios.delete(`/api/users/${targetUser.id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSystemUsers((prev) => prev.filter((u) => u.id !== targetUser.id));
      setActionSuccessMsg(`User "${targetUser.username}"was deleted successfully.`);
      fetchData(true);
      setTimeout(() => setActionSuccessMsg(""), 5000);
    } catch (err) {
      alert("Failed to delete user: " + (err.response?.data?.detail || err.message));
      fetchData(true);
    } finally {
      setUserDeletingId(null);
    }
  };

  const handleOpen2faSetup = async () => {
    setSetupVerifyError("");
    setSetupVerifyCode("");
    try {
      const res = await axios.get("/api/auth/2fa/setup", {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTwoFactorSetupData(res.data);
      setIs2faModalOpen(true);
    } catch (err) {
      alert("Failed to initiate 2FA setup: " + (err.response?.data?.detail || err.message));
    }
  };

  const handleOpen2faDisable = () => {
    setDisablePassword("");
    setIsDisable2faModalOpen(true);
  };

  const testServerConnection = async (urlToTest) => {
    setServerTestStatus({ loading: true, ok: false, msg: "Testing connection..." });
    const cleanUrl = (urlToTest || "").trim().replace(/\/$/, "");
    try {
      const res = await axios.get(`${cleanUrl}/api/health`, { timeout: 6000 });
      if (res.data?.status === "ok") {
        setServerTestStatus({ loading: false, ok: true, msg: "Connected successfully! Backend is online." });
      } else {
        setServerTestStatus({ loading: false, ok: true, msg: "Connected to server response." });
      }
    } catch (err) {
      setServerTestStatus({
        loading: false,
        ok: false,
        msg: `Cannot connect: ${err.message}. Ensure backend is running and URL is accessible.`
      });
    }
  };

  const handleSaveServerUrl = (newUrl) => {
    const cleanUrl = (newUrl || "").trim().replace(/\/$/, "");
    localStorage.setItem("mg_custom_api_url", cleanUrl);
    axios.defaults.baseURL = cleanUrl;
    setServerUrl(cleanUrl);
    setShowServerModal(false);
    setLoginError("");
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoginError("");
    try {
      const res = await axios.post("/api/auth/login", loginForm);
      if (res.data.requires_2fa) {
        // Switch to 2FA challenge mode
        setTwoFactorRequired(true);
        setTwoFactorTempToken(res.data.temp_token);
        setTwoFactorCode("");
        setTwoFactorMethod("totp");
        setTwoFactorEmailSent(false);
        setTwoFactorEmailPreview("");
        return;
      }
      const jwt = res.data.access_token;
      setToken(jwt);
      setUsername(res.data.username);
      localStorage.setItem("token", jwt);
      localStorage.setItem("username", res.data.username);
      if (res.data.refresh_token) {
        localStorage.setItem("refresh_token", res.data.refresh_token);
      }
    } catch (err) {
      if (!err.response) {
        setLoginError(
          `Cannot connect to backend server at "${axios.defaults.baseURL || "relative URL"}". Please tap "Server Settings"below to check your server address, and ensure the backend is running.`
        );
      } else if (err.response.status === 401) {
        setLoginError("Incorrect username or password. Please verify your credentials.");
      } else {
        setLoginError(err.response?.data?.detail || "Login failed. Please try again.");
      }
    }
  };

  const handleVerify2FA = async (e) => {
    e.preventDefault();
    if (!twoFactorCode.trim()) return;
    setLoginError("");
    setTwoFactorLoading(true);
    try {
      const res = await axios.post("/api/auth/2fa/verify", {
        code: twoFactorCode.trim(),
        temp_token: twoFactorTempToken
      });
      const jwt = res.data.access_token;
      setToken(jwt);
      setUsername(res.data.username);
      localStorage.setItem("token", jwt);
      localStorage.setItem("username", res.data.username);
      if (res.data.refresh_token) {
        localStorage.setItem("refresh_token", res.data.refresh_token);
      }
      setTwoFactorRequired(false);
      setTwoFactorTempToken("");
      setTwoFactorCode("");
    } catch (err) {
      if (!err.response) {
        setLoginError(`Cannot reach backend server at "${axios.defaults.baseURL}".`);
      } else {
        setLoginError(err.response?.data?.detail || "Invalid 2FA code. Please try again.");
      }
    } finally {
      setTwoFactorLoading(false);
    }
  };

  const handleCancel2FA = () => {
    setTwoFactorRequired(false);
    setTwoFactorTempToken("");
    setTwoFactorCode("");
    setTwoFactorEmailSent(false);
    setLoginError("");
  };

  const fetchRegistrationStatus = async () => {
    try {
      const res = await axios.get("/api/auth/registration-status");
      setRegistrationStatus(res.data);
    } catch (err) {
      console.error("Failed to fetch registration status:", err);
    }
  };

  useEffect(() => {
    fetchRegistrationStatus();
  }, [token]);

  useEffect(() => {
    const handleUnauthorized = () => {
      setToken("");
      setUsername("");
    };
    const handleTokenUpdated = (e) => {
      if (e?.detail?.token) {
        setToken(e.detail.token);
      }
    };
    window.addEventListener("auth:unauthorized", handleUnauthorized);
    window.addEventListener("auth:token-updated", handleTokenUpdated);
    return () => {
      window.removeEventListener("auth:unauthorized", handleUnauthorized);
      window.removeEventListener("auth:token-updated", handleTokenUpdated);
    };
  }, []);

  const handleRegister = async (e) => {
    e.preventDefault();
    setLoginError("");
    setAuthSuccess("");
    try {
      await axios.post("/api/auth/register", registerForm);
      setAuthSuccess(`Account for "${registerForm.username}" created successfully! Please sign in.`);
      setLoginForm({ username: registerForm.username, password: "" });
      setRegisterForm({ username: "", email: "", password: "" });
      setAuthMode("login");
      fetchRegistrationStatus();
    } catch (err) {
      if (!err.response) {
        setLoginError(`Cannot reach backend server at "${axios.defaults.baseURL}".`);
      } else {
        setLoginError(err.response?.data?.detail || "Registration failed. Try again.");
      }
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("username");
    localStorage.removeItem("refresh_token");
    delete axios.defaults.headers.common["Authorization"];
    setToken("");
    setUsername("");
  };

  // Fetch all data
  // POOL-SAFE: 14 requests split into 3 sequential batches of max 5.
  // pool_size=7, so running 5 at once leaves 2 connections free for the
  // scheduler (runs every 60s) and incoming Meta webhooks — preventing
  // "QueuePool limit of size 7 overflow 3 reached" errors that blank the UI.
  const fetchData = async (silent = false) => {
    if (!token) return;
    try {
      const headers = { Authorization: `Bearer ${token}` };

      // ── Priority 1: Instant First Paint Data ──
      // Fetch only what's required for dashboard/initial navigation
      const [contRes, wfRes, tmplRes, campRes] = await Promise.all([
        cachedGet("/api/contacts", { headers }, 30_000).catch((e) => { if (e.response?.status === 401) throw e; return { data: null }; }),
        cachedGet("/api/workflows", { headers }, 30_000).catch(() => ({ data: null })),
        cachedGet("/api/templates", { headers }, 30_000).catch(() => ({ data: null })),
        cachedGet("/api/campaigns", { headers }, 30_000).catch(() => ({ data: null })),
      ]);
      if (contRes.data !== null) setContacts(contRes.data);
      if (wfRes.data !== null) setWorkflowFlows(wfRes.data);
      if (tmplRes.data !== null) setTemplates(tmplRes.data);
      if (campRes.data !== null) setCampaigns(campRes.data);

      // Release the loading screen immediately so user enters dashboard in <150ms
      if (!silent) setLoading(false);

      // ── Priority 2: Streaming secondary data in background without blocking ──
      Promise.all([
        cachedGet("/api/automation-rules", { headers }, 60_000).catch(() => ({ data: null })),
        cachedGet("/api/settings", { headers }, 60_000).catch(() => ({ data: null })),
        cachedGet("/api/auth/me", { headers }, 60_000).catch(() => ({ data: null })),
        cachedGet("/api/cart-events", { headers }, 30_000).catch(() => ({ data: null })),
        cachedGet("/api/message-logs", { headers }, 30_000).catch(() => ({ data: null })),
      ]).then(([rulesRes, setRes, meRes, cartRes, logsRes]) => {
        if (rulesRes.data !== null) setAutomationRules(rulesRes.data);
        if (setRes.data !== null) setSystemSettings(setRes.data);
        if (meRes?.data) setCurrentUserProfile(meRes.data);
        if (cartRes.data !== null) setCartEvents(cartRes.data);
        if (logsRes.data !== null) setMessageLogs(logsRes.data);
      }).catch(console.error);

      // ── Priority 3: Lazy-loaded metadata (deferred, non-blocking) ──
      setTimeout(() => {
        Promise.all([
          cachedGet("/api/opt-outs", { headers }, 60_000).catch(() => ({ data: null })),
          cachedGet("/api/users", { headers }, 60_000).catch(() => ({ data: null })),
          cachedGet("/api/discount-codes", { headers }, 60_000).catch(() => ({ data: null })),
          cachedGet("/api/external-data-sources", { headers }, 60_000).catch(() => ({ data: null })),
        ]).then(([optRes, usersRes, discRes, extRes]) => {
          if (optRes.data !== null) setOptOuts(optRes.data);
          if (usersRes.data !== null) setSystemUsers(usersRes.data);
          if (discRes.data !== null) setDiscountCodes(discRes.data);
          if (extRes.data !== null) setExternalDataSources(extRes.data);
        }).catch(console.error);
      }, 500);

      // Only load chat conversations if currently on chat tab
      if (activeTab === "chat") {
        fetchChatConversations(true);
      }

      if (activeTab === "analytics") {
        fetchAnalytics(analyticsTimeRange, true);
      }
    } catch (err) {
      console.error("Failed to fetch protected data:", err);
      if (err.response?.status === 401) {
        handleLogout();
      }
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const fetchAnalytics = async (range = analyticsTimeRange, silent = false) => {
    if (!token) return;
    if (!silent) setAnalyticsLoading(true);
    try {
      const res = await axios.get(`/api/analytics/overview?time_range=${range}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setAnalyticsData(res.data);
    } catch (err) {
      if (!silent) console.error("Failed to fetch analytics overview:", err);
    } finally {
      if (!silent) setAnalyticsLoading(false);
    }
  };

  const isFetchingConversationsRef = useRef(false);

  const fetchChatConversations = async (silent = false) => {
    if (!token || isFetchingConversationsRef.current) return;
    isFetchingConversationsRef.current = true;
    try {
      const res = await axios.get("/api/chat/conversations", {
        headers: { Authorization: `Bearer ${token}` }
      });
      const convs = res.data || [];
      setChatConversations(convs);

      // Global check across all conversations for any new incoming customer message:
      const latestCustomerMsg = convs.find(
        (c) => c.last_sender === "CUSTOMER" && c.last_message_time
      );

      if (latestCustomerMsg) {
        const signature = `${latestCustomerMsg.customer_phone}-${latestCustomerMsg.last_message_time}-${latestCustomerMsg.last_message_text || ""}`;
        if (isInitialConversationsLoadRef.current) {
          isInitialConversationsLoadRef.current = false;
          lastKnownIncomingSignatureRef.current = signature;
        } else if (lastKnownIncomingSignatureRef.current !== signature) {
          lastKnownIncomingSignatureRef.current = signature;
          playIncomingMessageSound();
        }
      }
    } catch (err) {
      if (!silent) console.error("Failed to fetch chat conversations:", err);
    } finally {
      isFetchingConversationsRef.current = false;
    }
  };

  const fetchChatMessages = async (phone, silent = false) => {
    if (!token || !phone) return;
    if (!silent) setChatLoading(true);
    try {
      const res = await axios.get(`/api/chat/messages/${encodeURIComponent(phone)}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const newMsgs = res.data || [];
      
      // Secondary sound check if specific open thread receives a new message
      if (newMsgs.length > 0) {
        const lastMsg = newMsgs[newMsgs.length - 1];
        if (isInitialChatLoadRef.current) {
          isInitialChatLoadRef.current = false;
          lastProcessedMessageIdRef.current = lastMsg.id;
        } else if (
          lastMsg.id !== lastProcessedMessageIdRef.current &&
          lastMsg.sender_type === "CUSTOMER"
        ) {
          lastProcessedMessageIdRef.current = lastMsg.id;
          playIncomingMessageSound();
        } else {
          lastProcessedMessageIdRef.current = lastMsg.id;
        }
      }

      setChatMessages(newMsgs);
      // Update local unread counter for this conversation
      setChatConversations((prev) =>
        prev.map((c) => (c.customer_phone === phone ? { ...c, unread_count: 0 } : c))
      );
    } catch (err) {
      if (!silent) console.error("Failed to fetch messages for " + phone, err);
    } finally {
      if (!silent) setChatLoading(false);
    }
  };

  const handleSelectConversation = (phone) => {
    setSelectedChatPhone(phone);
    fetchChatMessages(phone, false);
  };

  const handleSendChatMessage = async (e) => {
    e?.preventDefault();
    if (!chatReplyText.trim() || !selectedChatPhone || chatSending) return;

    const messageText = chatReplyText.trim();
    setChatSending(true);

    // Optimistic local bubble
    const optimisticMsg = {
      id: "opt_" + Date.now(),
      customer_phone: selectedChatPhone,
      sender_type: "AGENT",
      message_type: "text",
      text: messageText,
      status: "SENDING",
      is_read: true,
      created_at: new Date().toISOString()
    };
    setChatMessages((prev) => [...prev, optimisticMsg]);
    setChatReplyText("");

    try {
      const res = await axios.post(
        "/api/chat/send",
        {
          customer_phone: selectedChatPhone,
          text: messageText
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      // Replace optimistic message with actual backend response
      setChatMessages((prev) =>
        prev.map((m) => (m.id === optimisticMsg.id ? res.data : m))
      );
      // Refresh conversation preview
      fetchChatConversations(true);
    } catch (err) {
      alert("Failed to send message: " + (err.response?.data?.detail || err.message));
      setChatMessages((prev) => prev.filter((m) => m.id !== optimisticMsg.id));
      setChatReplyText(messageText);
    } finally {
      setChatSending(false);
    }
  };

  const handleSendChatMedia = async ({ file, mediaType, caption }) => {
    if (!file || !selectedChatPhone || chatSending) return;

    setChatSending(true);
    const tempUrl = URL.createObjectURL(file);
    const optimisticMsg = {
      id: "opt_" + Date.now(),
      customer_phone: selectedChatPhone,
      sender_type: "AGENT",
      message_type: mediaType,
      text: caption || `[${mediaType.toUpperCase()}] ${file.name}`,
      media_url: tempUrl,
      filename: file.name,
      status: "SENDING",
      is_read: true,
      created_at: new Date().toISOString()
    };
    setChatMessages((prev) => [...prev, optimisticMsg]);

    try {
      const formData = new FormData();
      formData.append("customer_phone", selectedChatPhone);
      formData.append("media_type", mediaType);
      if (caption) formData.append("caption", caption);
      formData.append("file", file);

      const res = await axios.post("/api/chat/send-media", formData, {
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "multipart/form-data"
        }
      });

      setChatMessages((prev) =>
        prev.map((m) => (m.id === optimisticMsg.id ? res.data : m))
      );
      fetchChatConversations(true);
    } catch (err) {
      alert("Failed to send media: " + (err.response?.data?.detail || err.message));
      setChatMessages((prev) => prev.filter((m) => m.id !== optimisticMsg.id));
    } finally {
      setChatSending(false);
    }
  };

  const handleDeleteConversation = async (phone) => {
    if (!window.confirm(`Are you sure you want to delete all chat history with ${phone}? This cannot be undone.`)) {
      return;
    }
    try {
      await axios.delete(`/api/chat/conversations/${encodeURIComponent(phone)}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setChatMessages([]);
      setSelectedChatPhone("");
      fetchChatConversations(true);
      setActionSuccessMsg("Chat conversation deleted successfully.");
      setTimeout(() => setActionSuccessMsg(""), 4000);
    } catch (err) {
      alert("Failed to delete chat: " + (err.response?.data?.detail || err.message));
    }
  };

  const handleImportCsv = async (e) => {
    e.preventDefault();
    if (!csvFile) return;
    setCsvImporting(true);
    const formData = new FormData();
    formData.append("file", csvFile);

    try {
      const res = await axios.post("/api/contacts/import-csv", formData, {
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "multipart/form-data"
        }
      });
      setActionSuccessMsg(`${res.data.message}`);
      setIsCsvModalOpen(false);
      setCsvFile(null);
      fetchData();
      setTimeout(() => setActionSuccessMsg(""), 6000);
    } catch (err) {
      alert("Failed to import CSV: " + (err.response?.data?.detail || err.message));
    } finally {
      setCsvImporting(false);
    }
  };

  const handleOpenAddContact = () => {
    setEditingContactId(null);
    setContactForm({
      phone: "+91",
      name: "",
      email: "",
      city: "",
      tags: "",
      total_orders: 0,
      last_order_date: "",
      custom_attributes: {}
    });
    setIsContactModalOpen(true);
  };

  const handleOpenEditContact = (c) => {
    setEditingContactId(c.id);
    setContactForm({
      phone: c.phone || "",
      name: c.name || "",
      email: c.email || "",
      city: c.city || "",
      tags: c.tags || "",
      total_orders: Number(c.total_orders) || 0,
      last_order_date: c.last_order_date ? c.last_order_date.split("T")[0] : "",
      custom_attributes: c.custom_attributes || {}
    });
    setIsContactModalOpen(true);
  };

  const handleSaveContact = async (e) => {
    e.preventDefault();
    setContactSaving(true);
    try {
      const payload = {
        phone: contactForm.phone.trim(),
        name: contactForm.name.trim() || null,
        email: contactForm.email.trim() || null,
        city: contactForm.city.trim() || null,
        tags: contactForm.tags.trim() || null,
        total_orders: Number(contactForm.total_orders) || 0,
        last_order_date: contactForm.last_order_date ? contactForm.last_order_date : null,
        custom_attributes: contactForm.custom_attributes || {}
      };

      if (editingContactId) {
        const res = await axios.put(`/api/contacts/${editingContactId}`, payload, {
          headers: { Authorization: `Bearer ${token}` }
        });
        const updated = res.data;
        setContacts((prev) => prev.map((c) => (c.id === editingContactId ? { ...c, ...updated } : c)));
        setActionSuccessMsg(`Contact ${payload.phone} updated successfully!`);
      } else {
        const res = await axios.post("/api/contacts", payload, {
          headers: { Authorization: `Bearer ${token}` }
        });
        const created = res.data;
        setContacts((prev) => [created, ...prev]);
        setActionSuccessMsg(`Contact ${payload.phone} added successfully!`);
      }

      invalidateCache("/api/contacts");
      setIsContactModalOpen(false);
      setTimeout(() => setActionSuccessMsg(""), 5000);
    } catch (err) {
      alert("Failed to save contact: " + (err.response?.data?.detail || err.message));
    } finally {
      setContactSaving(false);
    }
  };

  const handleDeleteContact = async (c) => {
    if (!window.confirm(`Are you sure you want to delete contact ${c.phone} (${c.name || "Customer"})?`)) return;
    // Optimistically remove contact from UI immediately
    setContacts((prev) => prev.filter((contact) => contact.id !== c.id));
    setActionSuccessMsg(`Contact ${c.phone} deleted successfully!`);
    try {
      await axios.delete(`/api/contacts/${c.id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      invalidateCache("/api/contacts");
      setTimeout(() => setActionSuccessMsg(""), 5000);
    } catch (err) {
      alert("Failed to delete contact: " + (err.response?.data?.detail || err.message));
      invalidateCache("/api/contacts");
      fetchData(true); // rollback/re-sync if backend request failed
    }
  };

  const handleCreateDiscountCode = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        ...newDiscountCode,
        expires_at: newDiscountCode.expires_at ? new Date(newDiscountCode.expires_at).toISOString() : null
      };
      await axios.post("/api/discount-codes", payload, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setActionSuccessMsg(`Discount Code '${newDiscountCode.code}' created successfully!`);
      setIsDiscountModalOpen(false);
      setNewDiscountCode({
        code: "",
        discount_type: "PERCENT",
        discount_value: 10,
        min_order_value: 0,
        max_uses: 1000,
        expires_at: ""
      });
      fetchData();
      setTimeout(() => setActionSuccessMsg(""), 5000);
    } catch (err) {
      alert("Error creating discount code: " + (err.response?.data?.detail || err.message));
    }
  };

  const handleDeleteDiscountCode = async (id, code) => {
    if (!window.confirm(`Delete discount code ${code}?`)) return;
    try {
      await axios.delete(`/api/discount-codes/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      fetchData();
    } catch (err) {
      alert("Failed to delete discount code");
    }
  };

  const handleCreateTemplate = async (e) => {
    e.preventDefault();
    try {
      const res = await axios.post("/api/templates", newTemplate, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setActionSuccessMsg(`Template '${res.data.template_name}' submitted and saved!`);
      setIsTemplateModalOpen(false);
      setNewTemplate({
        template_name: "",
        category: "MARKETING",
        language: "en",
        header_text: "",
        body_text: "",
        footer_text: "JWL",
        variable_mappings: {}
      });
      invalidateCache("/api/templates");
      fetchData();
      setTimeout(() => setActionSuccessMsg(""), 6000);
    } catch (err) {
      alert("Failed to submit template: " + (err.response?.data?.detail || err.message));
    }
  };

  const handleSaveTemplateMappings = async () => {
    if (!editMappingTemplate) return;
    try {
      await axios.patch(`/api/templates/${editMappingTemplate.id}/mappings`,
        { variable_mappings: editMappings },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      invalidateCache("/api/templates");
      setActionSuccessMsg(`Column mappings saved for '${editMappingTemplate.template_name}'!`);
      setEditMappingTemplate(null);
      setEditMappings({});
      fetchData();
      setTimeout(() => setActionSuccessMsg(""), 5000);
    } catch (err) {
      alert("Failed to save mappings: " + (err.response?.data?.detail || err.message));
    }
  };


  useEffect(() => {
    if (token) {
      fetchData();
    }
  }, [token]);

  // Fetch analytics whenever user switches to Analytics tab or alters range
  useEffect(() => {
    if (token && activeTab === "analytics") {
      fetchAnalytics(analyticsTimeRange);
    }
  }, [token, activeTab, analyticsTimeRange]);

  // Instant eager load & high-frequency polling for Live Two-Way Chat (2.5s on active tab, 15s in background)
  useEffect(() => {
    if (!token) return;

    if (activeTab === "chat") {
      // Eager fetch immediately on switching to Live Chat tab
      fetchChatConversations(true);
      if (selectedChatPhone) {
        fetchChatMessages(selectedChatPhone, true);
      }
    }

    const pollInterval = activeTab === "chat" ? 2500 : 15000;
    const interval = setInterval(() => {
      fetchChatConversations(true);
      if (activeTab === "chat" && selectedChatPhone) {
        fetchChatMessages(selectedChatPhone, true);
      }
    }, pollInterval);
    return () => clearInterval(interval);
  }, [token, selectedChatPhone, activeTab]);

  // Periodic automatic silent background refresh for all views across the platform
  useEffect(() => {
    if (!token) return;
    // Auto-refresh every 20 seconds across all platform views to prevent worker saturation
    const interval = setInterval(() => {
      if (document.hidden) return; // Pause background polling if user switched away

      // 1. If full-screen Journey Analytics overlay is open, refresh its session funnel
      if (analyticsPage.open && analyticsPage.flow) {
        handleOpenAnalyticsPage(analyticsPage.flow, true);
      }

      // 2. Refresh main dataset across all tabs (Dashboard, Automations, Templates, Contacts, Campaigns, Logs, etc.)
      fetchData(true);

      // 3. If on analytics tab, also poll the comprehensive analytics dataset
      if (activeTab === "analytics") {
        fetchAnalytics(analyticsTimeRange, true);
      }
    }, 20000);
    return () => clearInterval(interval);
  }, [token, activeTab, analyticsPage.open, analyticsPage.flow, analyticsTimeRange]);


  const handleSyncMetaTemplates = async () => {
    setLoading(true);
    try {
      const res = await axios.post("/api/templates/sync-from-meta", {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      invalidateCache("/api/templates");
      setActionSuccessMsg(`${res.data.message}`);
      fetchData();
      setTimeout(() => setActionSuccessMsg(""), 5000);
    } catch (err) {
      alert("Failed to sync from Meta: " + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteTemplate = async (templateId, templateName) => {
    if (!window.confirm(`Are you sure you want to delete template "${templateName}"? This will remove it from your CRM catalog.`)) {
      return;
    }
    setLoading(true);
    try {
      const res = await axios.delete(`/api/templates/${templateId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      invalidateCache("/api/templates");
      setActionSuccessMsg(` ${res.data.message || "Template deleted successfully."}`);
      fetchData();
      setTimeout(() => setActionSuccessMsg(""), 5000);
    } catch (err) {
      alert("Failed to delete template: " + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleToggleRule = async (rule) => {
    try {
      await axios.patch(
        `/api/automation-rules/${rule.id}`,
        { is_active: !rule.is_active },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      invalidateCache("/api/automation-rules");
      fetchData();
    } catch (err) {
      alert("Failed to update rule status");
    }
  };

  // ── Multi-Step Visual Workflow Handlers ──────────────────────────────
  const handleSaveWorkflow = async (updatedFlow) => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      let res;
      if (updatedFlow.id) {
        res = await axios.put(`/api/workflows/${updatedFlow.id}`, updatedFlow, { headers });
      } else {
        res = await axios.post("/api/workflows", updatedFlow, { headers });
      }
      invalidateCache("/api/workflows");
      setActionSuccessMsg(`Workflow "${res.data.name}" saved successfully!`);
      setEditingWorkflow(null);
      fetchData();
      setTimeout(() => setActionSuccessMsg(""), 5000);
    } catch (err) {
      console.error("Failed to save workflow:", err);
      alert("Failed to save workflow: " + (err.response?.data?.detail || err.message));
    }
  };

  const handleToggleWorkflow = async (flow) => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const res = await axios.post(`/api/workflows/${flow.id}/toggle`, {}, { headers });
      invalidateCache("/api/workflows");
      setWorkflowFlows((prev) =>
        prev.map((f) => (f.id === flow.id ? res.data : f))
      );
      setActionSuccessMsg(`Workflow "${res.data.name}" is now ${res.data.is_active ? "Active" : "Paused"}`);
      setTimeout(() => setActionSuccessMsg(""), 4000);
    } catch (err) {
      console.error("Failed to toggle workflow:", err);
    }
  };

  const handleDeleteWorkflow = async (flowId) => {
    if (!window.confirm("Are you sure you want to delete this visual journey flow?")) return;
    try {
      const headers = { Authorization: `Bearer ${token}` };
      await axios.delete(`/api/workflows/${flowId}`, { headers });
      invalidateCache("/api/workflows");
      setWorkflowFlows((prev) => prev.filter((f) => f.id !== flowId));
      setActionSuccessMsg("Workflow deleted successfully.");
      setTimeout(() => setActionSuccessMsg(""), 4000);
    } catch (err) {
      console.error("Failed to delete workflow:", err);
    }
  };

  const handleCleanSlate = async () => {
    if (!window.confirm("Purge all sample workflows and rules? This will give you a 100% clean slate.")) return;
    try {
      const headers = { Authorization: `Bearer ${token}` };
      await axios.post("/api/automations/clean-slate", {}, { headers });
      setWorkflowFlows([]);
      setAutomationRules([]);
      setActionSuccessMsg("All sample workflows and automations purged. Clean slate active!");
      setTimeout(() => setActionSuccessMsg(""), 5000);
    } catch (err) {
      console.error("Clean slate failed:", err);
      // Fallback: delete each flow manually
      try {
        const headers = { Authorization: `Bearer ${token}` };
        for (const flow of workflowFlows) {
          await axios.delete(`/api/workflows/${flow.id}`, { headers });
        }
        for (const rule of automationRules) {
          await axios.delete(`/api/automation-rules/${rule.id}`, { headers });
        }
        setWorkflowFlows([]);
        setAutomationRules([]);
        setActionSuccessMsg("Sample automations deleted. Clean slate active!");
        setTimeout(() => setActionSuccessMsg(""), 5000);
      } catch (_e) {
        console.error("Fallback delete failed:", _e);
      }
    }
  };

  const handleCreateNewWorkflow = () => {
    handleOpenNewJourneyModal();
  };

  const handleTriggerRule = async (rule) => {
    try {
      const res = await axios.post(
        `/api/automation-rules/${rule.id}/trigger`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );

      if (res.data.requires_approval) {
        // Intercept: More than 100 recipients! Open step-up 2FA approval modal
        setSecurityActionModal({
          isOpen: true,
          actionType: "AUTOMATION_APPROVAL",
          title: `Approve High-Volume Automation: "${rule.rule_name}"`,
          recipientCount: res.data.eligible_count,
          payloadData: { ruleId: rule.id, ruleName: rule.rule_name },
          password: "",
          twoFactorCode: "",
          error: "",
          loading: false
        });
        fetchData();
        return;
      }

      setActionSuccessMsg(`Automation '${rule.rule_name}' executed: ${res.data.messages_dispatched} messages sent (dedup applied).`);
      fetchData();
      setTimeout(() => setActionSuccessMsg(""), 6000);
    } catch (err) {
      alert("Failed to trigger rule: " + (err.response?.data?.detail || err.message));
    }
  };



  const handleCreateCampaign = async (e) => {
    e.preventDefault();
    if (!newCampaign.title || !token) return;

    // Calculate approximate recipient count for confirmation (capped by per_day_limit if set)
    let estCount =
      newCampaign.target_filter === "INACTIVE_30_DAYS"
        ? contacts.filter((c) => !c.last_order_date).length || 5
        : contacts.length;

    const parsedLimit = newCampaign.per_day_limit ? parseInt(newCampaign.per_day_limit, 10) : null;
    if (parsedLimit && parsedLimit > 0) {
      estCount = Math.min(estCount, parsedLimit);
    }

    try {
      const payload = {
        ...newCampaign,
        scheduled_for: newCampaign.scheduled_for
          ? (newCampaign.scheduled_for.includes("+") || newCampaign.scheduled_for.endsWith("Z")
              ? newCampaign.scheduled_for
              : (newCampaign.scheduled_for.length === 16 ? `${newCampaign.scheduled_for}:00+05:30` : `${newCampaign.scheduled_for}+05:30`))
          : null,
        per_day_limit: parsedLimit && parsedLimit > 0 ? parsedLimit : null
      };

      const res = await axios.post("/api/campaigns", payload, {
        headers: { Authorization: `Bearer ${token}` }
      });

      setActionSuccessMsg(`Broadcast Campaign '${payload.title}'launched successfully!`);
      setIsModalOpen(false);
      const approvedTmpl = templates.find((t) => t.status === "APPROVED") || templates[0];
      setNewCampaign({
        title: "",
        template_name: approvedTmpl ? approvedTmpl.template_name : "",
        language: approvedTmpl ? (approvedTmpl.language || "en") : "en",
        target_filter: "ALL",
        per_day_limit: "",
        scheduled_for: ""
      });
      invalidateCache("/api/campaigns");
      if (res.data) {
        setCampaigns((prev) => [res.data, ...prev.filter((c) => c.id !== res.data.id)]);
      }
      setTimeout(() => setActionSuccessMsg(""), 6000);
    } catch (err) {
      alert("Failed to launch campaign: " + (err.response?.data?.detail || err.message));
    }
  };

  const handleExecuteSecurityAction = async (e) => {
    e.preventDefault();
    const { actionType, payloadData, password, twoFactorCode } = securityActionModal;
    if (!password) {
      setSecurityActionModal((prev) => ({ ...prev, error: "Please enter your account password." }));
      return;
    }

    setSecurityActionModal((prev) => ({ ...prev, loading: true, error: "" }));

    try {
      if (actionType === "CAMPAIGN") {
        await axios.post(
          "/api/campaigns",
          {
            ...payloadData,
            password: password,
            two_factor_code: twoFactorCode.trim()
          },
          { headers: { Authorization: `Bearer ${token}` } }
        );

        setActionSuccessMsg(`Broadcast Campaign '${payloadData.title}'successfully verified with 2FA and queued for dispatch!`);
        setIsModalOpen(false);
        setSecurityActionModal((prev) => ({ ...prev, isOpen: false }));
        const approvedTmpl = templates.find((t) => t.status === "APPROVED") || templates[0];
        setNewCampaign({
          title: "",
          template_name: approvedTmpl ? approvedTmpl.template_name : "",
          language: approvedTmpl ? (approvedTmpl.language || "en") : "en",
          target_filter: "ALL",
          per_day_limit: "",
          scheduled_for: ""
        });
        fetchData();
        setTimeout(() => setActionSuccessMsg(""), 6000);

      } else if (actionType === "AUTOMATION_APPROVAL") {
        const res = await axios.post(
          `/api/automation-rules/${payloadData.ruleId}/approve`,
          {
            password: password,
            two_factor_code: twoFactorCode.trim()
          },
          { headers: { Authorization: `Bearer ${token}` } }
        );

        setActionSuccessMsg(` ${res.data.message}`);
        setSecurityActionModal((prev) => ({ ...prev, isOpen: false }));
        fetchData();
        setTimeout(() => setActionSuccessMsg(""), 6000);
      }
    } catch (err) {
      setSecurityActionModal((prev) => ({
        ...prev,
        loading: false,
        error: err.response?.data?.detail || err.response?.data?.message || err.message || "Authorization failed."
      }));
    }
  };

  const handleCancelCampaign = async (campaignId) => {
    if (!window.confirm(`Cancel scheduled broadcast #${campaignId}? It will not be sent.`)) return;
    try {
      await axios.delete(`/api/campaigns/${campaignId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setActionSuccessMsg(`Scheduled campaign #${campaignId} has been cancelled.`);
      fetchData();
      setTimeout(() => setActionSuccessMsg(""), 5000);
    } catch (err) {
      alert("Failed to cancel campaign: " + (err.response?.data?.detail || err.message));
    }
  };

  const handleRemoveOptOut = async (phone) => {
    if (!window.confirm(`Remove ${phone} from Opt-Out (DND) list?`)) return;
    try {
      await axios.delete(`/api/opt-outs/${encodeURIComponent(phone)}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      fetchData();
    } catch (err) {
      alert("Error removing opt-out: " + (err.response?.data?.detail || err.message));
    }
  };

  const totalRecoveredValue = cartEvents
    .filter((c) => c.status === "RECOVERED")
    .reduce((sum, c) => sum + (c.cart_value || 0), 0);

  // If unauthenticated, show login/register screen
  if (!token) {
    return (
      <LoginView
        serverUrl={serverUrl}
        loginError={loginError}
        authSuccess={authSuccess}
        twoFactorRequired={twoFactorRequired}
        twoFactorMethod={twoFactorMethod}
        twoFactorEmailPreview={twoFactorEmailPreview}
        twoFactorCode={twoFactorCode}
        setTwoFactorCode={setTwoFactorCode}
        twoFactorLoading={twoFactorLoading}
        handleVerify2FA={handleVerify2FA}
        handleCancel2FA={handleCancel2FA}
        loginForm={loginForm}
        setLoginForm={setLoginForm}
        showPassword={showPassword}
        setShowPassword={setShowPassword}
        handleLogin={handleLogin}
        showServerModal={showServerModal}
        setShowServerModal={setShowServerModal}
        serverInput={serverInput}
        setServerInput={setServerInput}
        serverTestStatus={serverTestStatus}
        setServerTestStatus={setServerTestStatus}
        testServerConnection={testServerConnection}
        handleSaveServerUrl={handleSaveServerUrl}
        renderProdUrl={RENDER_PROD_URL}
      />
    );
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#F8F9FA] text-[#111827]">
      {/* ── Left Sidebar (Collapsible) ── */}
      <aside
        className={`${
          sidebarCollapsed ? "w-16" : "w-64"
        } flex-shrink-0 bg-[#111827] text-gray-300 flex flex-col justify-between border-r border-gray-800 transition-all duration-300 ease-in-out relative`}
      >
        {/* Sidebar Collapse / Expand Floating Toggle */}
        <button
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          className="absolute -right-3 top-6 z-30 w-6 h-6 rounded-full bg-[#F5A623] hover:bg-[#E67E22] text-black flex items-center justify-center shadow-md transition transform hover:scale-110"
          title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {sidebarCollapsed ? (
            <ChevronRight className="w-3.5 h-3.5" />
          ) : (
            <ChevronLeft className="w-3.5 h-3.5" />
          )}
        </button>

        <div>
          {/* Brand Header */}
          <div className={`p-4 flex items-center ${sidebarCollapsed ? "justify-center" : "gap-3"} border-b border-gray-800`}>
            <div className="w-10 h-10 rounded-lg bg-[#F5A623] flex items-center justify-center font-bold text-black text-xl shadow-md flex-shrink-0">
              S
            </div>
            {!sidebarCollapsed && (
              <div className="overflow-hidden whitespace-nowrap">
                <h1 className="font-bold text-white text-base leading-tight">Scalifts</h1>
                <span className="text-xs text-[#F5A623] font-medium tracking-wide">WhatsApp CRM</span>
              </div>
            )}
          </div>

          {/* Navigation Links */}
          <nav className="p-2 space-y-1.5 mt-2">
            {[
              { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
              {
                id: "chat",
                label: "Live Chat / Inbox",
                icon: MessageSquare,
                badge: chatConversations.reduce((acc, c) => acc + (c.unread_count || 0), 0)
              },
              { id: "automations", label: "Automations", icon: Sliders, badge: workflowFlows.length },
              { id: "campaigns", label: "Campaigns", icon: Megaphone },
              { id: "analytics", label: "Analytics", icon: BarChart3 },
              { id: "templates", label: "Templates", icon: BookOpen, badge: templates.length },
              { id: "contacts", label: "Contacts", icon: Users },
              { id: "logs", label: "Message Logs", icon: FileText },
              { id: "opt_out", label: "Opt-Out (DND)", icon: ShieldBan, badge: optOuts.length },
              { id: "settings", label: "Settings", icon: Settings },
            ].map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleTabChange(item.id)}
                  title={sidebarCollapsed ? item.label : undefined}
                  className={`w-full flex items-center ${
                    sidebarCollapsed ? "justify-center px-0 py-2.5" : "justify-between px-3.5 py-2.5"
                  } rounded-lg text-sm font-medium transition-all relative group ${
                    isActive
                      ? `bg-[#1F2937] text-[#F5A623] ${!sidebarCollapsed ? "border-l-4 border-[#F5A623]" : "ring-1 ring-[#F5A623]"}`
                      : "hover:bg-gray-800/60 hover:text-white"
                  }`}
                >
                  <div className={`flex items-center ${sidebarCollapsed ? "justify-center" : "gap-3"}`}>
                    <Icon className={`w-5 h-5 flex-shrink-0 ${isActive ? "text-[#F5A623]" : "text-gray-400"}`} />
                    {!sidebarCollapsed && <span>{item.label}</span>}
                  </div>

                  {/* Badge */}
                  {item.badge !== undefined && item.badge > 0 && (
                    <span
                      className={`${
                        sidebarCollapsed
                          ? "absolute -top-1 -right-1 min-w-[16px] h-4 text-[9px] px-1 flex items-center justify-center font-black rounded-full"
                          : "px-2 py-0.5 text-xs font-bold rounded-full"
                      } ${
                        item.id === "opt_out"
                          ? "bg-red-900/80 text-red-200 border border-red-700"
                          : item.id === "chat"
                          ? "bg-[#25D366] text-black font-black animate-pulse shadow-sm shadow-green-500/50"
                          : item.id === "automations"
                          ? "bg-emerald-900/80 text-[#25D366] border border-emerald-700"
                          : "bg-amber-900/80 text-[#F5A623] border border-amber-700"
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}

                  {/* Tooltip on hover when collapsed */}
                  {sidebarCollapsed && (
                    <div className="absolute left-full ml-2.5 px-2.5 py-1 bg-gray-900 text-white text-xs font-semibold rounded-md opacity-0 group-hover:opacity-100 pointer-events-none transition shadow-lg whitespace-nowrap z-50">
                      {item.label}
                    </div>
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Bottom Status & Logout */}
        <div className="p-3 border-t border-gray-800 space-y-2">
          {!sidebarCollapsed ? (
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-[#25D366] animate-pulse"></span>
                <span className="text-gray-300 font-semibold truncate max-w-[120px]">{username}</span>
              </div>
              <button
                onClick={handleLogout}
                className="flex items-center gap-1 text-gray-400 hover:text-red-400 transition"
                title="Logout"
              >
                <LogOut className="w-3.5 h-3.5" />
                Exit
              </button>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-[#25D366] animate-pulse" title={`Logged in as ${username}`}></span>
              <button
                onClick={handleLogout}
                className="p-1 text-gray-400 hover:text-red-400 transition rounded"
                title="Logout"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* ── Main Content Area ── */}
      <main className={`flex-1 flex flex-col ${activeTab === "chat" ? "overflow-hidden h-screen" : "overflow-y-auto"}`}>
        {/* Top App Bar */}
        <header className="h-16 bg-white border-b border-gray-200 px-8 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-gray-900 capitalize">
              {activeTab === "opt_out"
                ? "Opt-Out (DND) Registry"
                : activeTab === "chat"
                ? "Two-Way WhatsApp Live Chat / Inbox"
                : activeTab === "analytics"
                ? "Delivery & Engagement Analytics"
                : activeTab === "performance"
                ? "System Performance & NOC Live Center"
                : activeTab === "templates"
                ? "WhatsApp Template Messages (Doc 04)"
                : activeTab === "automations"
                ? "Automation Triggers & Rules"
                : activeTab.replace("_", " ")}
            </h2>
          </div>
          <div className="flex items-center gap-3">
            {activeTab !== "campaigns" && (
              <button
                onClick={fetchData}
                disabled={loading}
                className="p-2 border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600 transition"
                title="Refresh data"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              </button>
            )}

            {activeTab === "automations" && (
              <button
                onClick={handleOpenNewJourneyModal}
                className="flex items-center gap-2 bg-[#25D366] hover:bg-[#1EBE5D] text-white px-4 py-2 rounded-lg font-bold text-sm shadow-sm transition"
              >
                <Plus className="w-4 h-4" />
                <span>Create Journey Flow</span>
              </button>
            )}

            {activeTab === "dashboard" && (
              <button
                onClick={handleOpenCampaignModal}
                className="flex items-center gap-2 bg-[#25D366] hover:bg-[#1EBE5D] text-white px-4 py-2 rounded-lg font-semibold text-sm shadow-sm transition shadow-green-500/20"
              >
                <Plus className="w-4 h-4" />
                New Broadcast Campaign
              </button>
            )}
          </div>
        </header>

        {/* Action Toast / Success Banner */}
        {actionSuccessMsg && (
          <div className="mx-8 mt-4 p-3.5 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs font-semibold flex items-center justify-between">
            <span>{actionSuccessMsg}</span>
            <button onClick={() => setActionSuccessMsg("")} className="text-emerald-600 font-bold"></button>
          </div>
        )}

        {/* Dynamic Views */}
        <div className={activeTab === "chat" ? "p-3 md:p-5 flex-1 flex flex-col min-h-0 overflow-hidden" : "p-8 space-y-6"}>
          {activeTab === "dashboard" && (
            <DashboardPage
              workflowFlows={workflowFlows}
              messageLogs={messageLogs}
              cartEvents={cartEvents}
              campaigns={campaigns}
              contacts={contacts}
              optOuts={optOuts}
              handleTabChange={handleTabChange}
              setEditingWorkflow={setEditingWorkflow}
              handleOpenNewJourneyModal={handleOpenNewJourneyModal}
            />
          )}



          {activeTab === "automations" && (
            <AutomationsPage
              editingWorkflow={editingWorkflow}
              setEditingWorkflow={setEditingWorkflow}
              handleSaveWorkflow={handleSaveWorkflow}
              templates={templates}
              discountCodes={discountCodes}
              workflowFlows={workflowFlows}
              handleCleanSlate={handleCleanSlate}
              handleOpenNewJourneyModal={handleOpenNewJourneyModal}
              cartEvents={cartEvents}
              messageLogs={messageLogs}
              optOuts={optOuts}
              campaigns={campaigns}
              contacts={contacts}
              handleToggleWorkflow={handleToggleWorkflow}
              handleDeleteWorkflow={handleDeleteWorkflow}
              handleOpenJourneySessions={handleOpenJourneySessions}
              handleOpenAnalyticsPage={handleOpenAnalyticsPage}
            />
          )}

          {activeTab === "settings" && (
            <SettingsPage
              systemSettings={systemSettings}
              setSystemSettings={setSystemSettings}
              currentUserProfile={currentUserProfile}
              setIsAddUserModalOpen={setIsAddUserModalOpen}
              systemUsers={systemUsers}
              username={username}
              handleDeleteUser={handleDeleteUser}
              userRoleUpdatingId={userRoleUpdatingId}
              userDeletingId={userDeletingId}
              handleUpdateUserRole={handleUpdateUserRole}
              setAdminPasswordModal={setAdminPasswordModal}
              admin2faUpdatingId={admin2faUpdatingId}
              handleAdminToggle2FA={handleAdminToggle2FA}
              handleOpen2faSetup={handleOpen2faSetup}
              handleOpen2faDisable={handleOpen2faDisable}
              setIsRoleInfoModalOpen={setIsRoleInfoModalOpen}
              setAddUserError={setAddUserError}
              setSystemUsers={setSystemUsers}
            />
          )}


          {activeTab === "templates" && (
            <TemplatesPage
              templates={templates}
              setIsTemplateModalOpen={setIsTemplateModalOpen}
              handleDeleteTemplate={handleDeleteTemplate}
              handleSyncMetaTemplates={handleSyncMetaTemplates}
              loading={loading}
              templateFilterLang={templateFilterLang}
              setTemplateFilterLang={setTemplateFilterLang}
              templatePage={templatePage}
              setTemplatePage={setTemplatePage}
              setEditMappingTemplate={setEditMappingTemplate}
              setEditMappings={setEditMappings}
            />
          )}


          {activeTab === "campaigns" && (
            <CampaignsPage
              campaigns={campaigns}
              handleOpenCampaignModal={handleOpenCampaignModal}
              handleCancelScheduledCampaign={handleCancelCampaign}
              token={token}
              handleTabChange={handleTabChange}
            />
          )}


          {activeTab === "analytics" && (
            <AnalyticsPage
              analyticsTimeRange={analyticsTimeRange}
              setAnalyticsTimeRange={setAnalyticsTimeRange}
              fetchAnalytics={fetchAnalytics}
              handleSyncMetaTemplates={handleSyncMetaTemplates}
              loading={loading}
              analyticsLoading={analyticsLoading}
              analyticsData={analyticsData}
              handleTabChange={handleTabChange}
            />
          )}

          {activeTab === "performance" && (
            <PerformanceNocPage
              token={token}
              handleTabChange={handleTabChange}
            />
          )}

          {activeTab === "contacts" && (
            <ContactsPage
              contacts={contacts}
              contactsPerPage={contactsPerPage}
              setContactsPerPage={setContactsPerPage}
              setContactsPage={setContactsPage}
              contactsPage={contactsPage}
              searchTerm={searchTerm}
              setSearchTerm={setSearchTerm}
              contactFilterCity={contactFilterCity}
              setContactFilterCity={setContactFilterCity}
              contactFilterTag={contactFilterTag}
              setContactFilterTag={setContactFilterTag}
              contactFilterVip={contactFilterVip}
              setContactFilterVip={setContactFilterVip}
              contactFilterOrders={contactFilterOrders}
              setContactFilterOrders={setContactFilterOrders}
              contactSortField={contactSortField}
              setContactSortField={setContactSortField}
              contactSortOrder={contactSortOrder}
              setContactSortOrder={setContactSortOrder}
              handleDeleteContact={handleDeleteContact}
              handleOpenAddContact={handleOpenAddContact}
              handleOpenEditContact={handleOpenEditContact}
              setIsCsvModalOpen={setIsCsvModalOpen}
            />
          )}

          {activeTab === "logs" && (
            <MessageLogsPage
              messageLogs={messageLogs}
              onRefresh={() => fetchData(true)}
              token={token}
              onShowToast={(msg) => {
                setActionSuccessMsg(msg);
                setTimeout(() => setActionSuccessMsg(""), 5000);
              }}
            />
          )}

          {activeTab === "opt_out" && (
            <OptOutPage
              optOuts={optOuts}
              handleRemoveOptOut={handleRemoveOptOut}
            />
          )}

          {activeTab === "chat" && (
            <LiveChatPage
              chatConversations={chatConversations}
              chatMessages={chatMessages}
              selectedChatPhone={selectedChatPhone}
              chatLoading={chatLoading}
              chatSending={chatSending}
              chatReplyText={chatReplyText}
              setChatReplyText={setChatReplyText}
              chatFilterUnreadOnly={chatFilterUnreadOnly}
              setChatFilterUnreadOnly={setChatFilterUnreadOnly}
              chatListCollapsed={chatListCollapsed}
              setChatListCollapsed={setChatListCollapsed}
              chatSoundEnabled={chatSoundEnabled}
              setChatSoundEnabled={setChatSoundEnabled}
              playIncomingMessageSound={playIncomingMessageSound}
              searchTerm={searchTerm}
              setSearchTerm={setSearchTerm}
              contacts={contacts}
              handleSelectConversation={handleSelectConversation}
              fetchChatMessages={fetchChatMessages}
              handleSendChatMessage={handleSendChatMessage}
              handleSendChatMedia={handleSendChatMedia}
              handleDeleteConversation={handleDeleteConversation}
            />
          )}
        </div>
      </main>

      {/* ── Extracted Modular Modals ── */}
      <AddUserModal
        isOpen={isAddUserModalOpen}
        onClose={() => setIsAddUserModalOpen(false)}
        systemUsers={systemUsers}
        newUserForm={newUserForm}
        setNewUserForm={setNewUserForm}
        addUserLoading={addUserLoading}
        addUserError={addUserError}
        onSubmit={handleCreateUserFromSettings}
      />

      <JourneySessionsModal
        modalState={journeySessionsModal}
        setModalState={setJourneySessionsModal}
        onOpenAnalyticsPage={handleOpenAnalyticsPage}
      />

      {/* Full-screen Automation Analytics Page */}
      {analyticsPage.open && (
        <div className="fixed inset-0 z-50 bg-white overflow-hidden">
          <AutomationAnalyticsPage
            flow={analyticsPage.flow}
            sessions={analyticsPage.sessions}
            loading={analyticsPage.loading}
            token={token}
            onRefresh={() => handleOpenAnalyticsPage(analyticsPage.flow, true)}
            onBack={() => setAnalyticsPage(prev => ({ ...prev, open: false }))}
          />
        </div>
      )}

      <NewJourneyModal
        isOpen={isNewJourneyModalOpen}
        onClose={() => setIsNewJourneyModalOpen(false)}
        newJourneyForm={newJourneyForm}
        setNewJourneyForm={setNewJourneyForm}
        onConfirm={handleConfirmCreateJourney}
      />

      <CampaignModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        newCampaign={newCampaign}
        setNewCampaign={setNewCampaign}
        templates={templates}
        contacts={contacts}
        onSubmit={handleCreateCampaign}
      />

      <SecurityActionModal
        modalState={securityActionModal}
        setModalState={setSecurityActionModal}
        onExecute={handleExecuteSecurityAction}
      />

      <CsvImportModal
        isOpen={isCsvModalOpen}
        onClose={() => setIsCsvModalOpen(false)}
        csvFile={csvFile}
        setCsvFile={setCsvFile}
        csvImporting={csvImporting}
        onSubmit={handleImportCsv}
      />

      <ContactModal
        isOpen={isContactModalOpen}
        onClose={() => setIsContactModalOpen(false)}
        editingContactId={editingContactId}
        contactForm={contactForm}
        setContactForm={setContactForm}
        contactSaving={contactSaving}
        onSave={handleSaveContact}
      />

      <TemplateModal
        isOpen={isTemplateModalOpen}
        onClose={() => setIsTemplateModalOpen(false)}
        newTemplate={newTemplate}
        setNewTemplate={setNewTemplate}
        onSubmit={handleCreateTemplate}
      />

      <TemplateMappingModal
        editMappingTemplate={editMappingTemplate}
        editMappings={editMappings}
        setEditMappings={setEditMappings}
        onClose={() => { setEditMappingTemplate(null); setEditMappings({}); }}
        onSave={handleSaveTemplateMappings}
      />

      <TwoFactorSetupModal
        isOpen={is2faModalOpen}
        onClose={() => setIs2faModalOpen(false)}
        setupData={twoFactorSetupData}
        verifyCode={setupVerifyCode}
        setVerifyCode={setSetupVerifyCode}
        verifyLoading={setupVerifyLoading}
        verifyError={setupVerifyError}
        onConfirm={async (e) => {
          e.preventDefault();
          if (!setupVerifyCode.trim()) return;
          setSetupVerifyLoading(true);
          setSetupVerifyError("");
          try {
            await axios.post(
              "/api/auth/2fa/enable",
              { code: setupVerifyCode.trim() },
              { headers: { Authorization: `Bearer ${token}` } }
            );
            setActionSuccessMsg("Two-Factor Authentication (2FA) successfully activated!");
            setIs2faModalOpen(false);
            fetchData();
            setTimeout(() => setActionSuccessMsg(""), 5000);
          } catch (err) {
            setSetupVerifyError(err.response?.data?.detail || "Invalid code. Please try again.");
          } finally {
            setSetupVerifyLoading(false);
          }
        }}
      />

      <TwoFactorDisableModal
        isOpen={isDisable2faModalOpen}
        onClose={() => setIsDisable2faModalOpen(false)}
        disablePassword={disablePassword}
        setDisablePassword={setDisablePassword}
        disableLoading={disableLoading}
        onSubmit={async (e) => {
          e.preventDefault();
          setDisableLoading(true);
          try {
            await axios.post(
              "/api/auth/2fa/disable",
              { password: disablePassword },
              { headers: { Authorization: `Bearer ${token}` } }
            );
            setActionSuccessMsg("Two-Factor Authentication has been turned off.");
            setIsDisable2faModalOpen(false);
            fetchData();
            setTimeout(() => setActionSuccessMsg(""), 5000);
          } catch (err) {
            alert(err.response?.data?.detail || "Failed to disable 2FA");
          } finally {
            setDisableLoading(false);
          }
        }}
      />

      <AdminPasswordModal
        modalState={adminPasswordModal}
        setModalState={setAdminPasswordModal}
        onSubmit={handleAdminResetPassword}
      />

      <RoleInfoModal
        isOpen={isRoleInfoModalOpen}
        onClose={() => setIsRoleInfoModalOpen(false)}
      />

    </div>
  );
}
