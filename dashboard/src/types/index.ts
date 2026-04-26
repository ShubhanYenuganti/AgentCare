// Shared TypeScript interfaces for AgentCare dashboard API responses

export interface LifeGraph {
  health?: {
    medications?: Array<{
      name: string;
      dose: string;
      frequency: string;
      last_refill?: string | null;
      next_refill_due?: string | null;
    }>;
    conditions?: string[];
    allergies?: string[];
    last_physical?: string | null;
  };
  appointments?: Array<{
    date: string;
    provider: string;
    type: string;
    completed?: boolean;
    transport_needed?: boolean;
  }>;
  grocery?: {
    last_delivery?: string | null;
    dietary_restrictions?: string[];
    staples?: string[];
    supplies?: Record<string, number>;
  };
  financial?: {
    bills?: Array<{
      name: string;
      amount: number;
      due_date: string;
      autopay?: boolean;
    }>;
    spending_history?: Array<{
      date: string;
      amount: number;
      category: string;
    }>;
  };
  emergency_contacts?: Array<{
    name: string;
    relationship: string;
    phone: string;
  }>;
  [key: string]: unknown;
}

export interface Patient {
  patient_id: string;
  name: string;
  age: number | null;
  address: string | null;
  active: number;
  preferences_json: Record<string, unknown>;
  life_graph_json: LifeGraph;
  // Enriched fields
  pending_action_count?: number;
  overdue_action_count?: number;
  highest_urgency_level?: string | null;
}

export interface ExecutionPlanStep {
  kind: string;
  route: string;
  method?: string;
  preflight_errors?: string[];
}

export interface ExecutionPlan {
  steps: ExecutionPlanStep[];
  inferred_route?: string | null;
  route_source?: string;
}

export interface Action {
  action_id: string;
  patient_id: string;
  patient_name?: string;
  domain: string;
  type: string;
  description: string;
  urgency_level: string;
  urgency_score?: number;
  review_by: string | null;
  is_overdue: number;
  completed: number;
  draft_content: string | null;
  modification_in_progress?: number;
  idempotency_key?: string | null;
  manual_action_type?: string | null;
  schedule?: { start_time: string; end_time: string; recurrence?: { day: string; freq: string } } | null;
  assigned_caregiver?: string | null;
  created_at?: string;
  recipient_email?: string | null;
  recipient_type?: string | null;
  email_subject?: string | null;
  api_payload?: Record<string, unknown> | null;
  execution_plan?: ExecutionPlan;
  /** When loaded from action history: approved / dismissed / … */
  outcome?: string | null;
  /** Completion timestamp when `completed=1` */
  completion_date?: string | null;
}

export interface ChatMessage {
  message_id?: string;
  action_id: string;
  role: "user" | "assistant";
  content: string;
  created_at?: string;
}

export interface Caregiver {
  caregiver_id: string;
  name: string;
  availability_today: boolean;
  booked_today: boolean;
  assignments?: Array<{
    patient_id: string;
    name: string;
    pending_actions: number;
  }>;
}

export interface CaregiverScheduleSlot {
  date: string;
  /** Present when the API enriches the row; otherwise derive from `booked` / `available`. */
  shift?: string;
  status?: "available" | "booked" | "unavailable";
  /** SQLite 0/1 from `caregiver_schedule` */
  available?: number;
  booked?: number;
  start_time?: string | null;
  end_time?: string | null;
  patient_id?: string | null;
  patient_name?: string | null;
}

export interface OrgProfile {
  id?: number;
  org_name?: string;
  care_philosophy?: string;
  escalation_chain?: string;
  escalation_lead?: string;
  protocols?: Array<{
    name: string;
    description: string;
    domain: string;
  }>;
  caregiver_count?: number;
  patient_count?: number;
}

export interface SchedulingOption {
  option_id: string;
  action_id: string;
  caregiver_id: string;
  caregiver_name: string;
  proposed_date: string;
  proposed_time: string;
  notes?: string;
}

export interface CaregiverAssignment {
  action_id: string;
  description: string;
  type: string;
  schedule: string | null;
  domain?: string | null;
  manual_action_type?: string | null;
  urgency_level?: string | null;
  review_by?: string | null;
  draft_content?: string | null;
  patient_name: string;
  caregiver_name: string;
}

export interface SetupStatus {
  org_configured: boolean;
  caregiver_count: number;
  patient_count: number;
}

export interface DaySchedule {
  start: string;
  end: string;
}

export interface CreateCaregiverBody {
  name: string;
  email: string;
  phone: string;
  role: "caregiver" | "admin";
  schedule: Partial<Record<"Mon" | "Tue" | "Wed" | "Thu" | "Fri" | "Sat" | "Sun", DaySchedule>>;
}

export interface PatientUpdate {
  update_id: string;
  patient_id: string;
  submitted_at: string;
  status: "pending" | "confirmed" | "cancelled";
  update_text?: string;
  proposed_changes?: Record<string, unknown>;
  domain?: string;
  summary?: string;
  /** True when row was written by /ingest audit (file or text), not the staged /update flow */
  fromIngest?: boolean;
}

// General chat session types
export interface GeneralChatMessage {
  id: number;
  role: "user" | "agent";
  content: string;
  stage?: string;
  intent_class?: string | null;
  domain?: string | null;
  patient_ids?: string[];
  draft_action_id?: string | null;
  created_at?: string;
}

export interface SendMessageResponse {
  session_id: string;
  reply: string;
  stage: string;
  draft_action_id?: string | null;
  intent_class?: string | null;
  domain?: string | null;
}

export interface StagedActionDraft {
  patient_id?: string;
  domain?: string;
  type?: string;
  description?: string;
  schedule?: Record<string, unknown>;
  [key: string]: unknown;
}
