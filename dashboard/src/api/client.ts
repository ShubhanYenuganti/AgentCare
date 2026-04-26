import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import type {
  Action,
  Caregiver,
  CaregiverAssignment,
  CaregiverScheduleSlot,
  ChatMessage,
  CreateCaregiverBody,
  GeneralChatMessage,
  OrgProfile,
  Patient,
  PatientUpdate,
  SchedulingOption,
  SendMessageResponse,
  SetupStatus,
} from "../types";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

/** Response body from POST /ingest/text and /ingest/file */
export type IngestResult = {
  patient_id: string;
  extracted: unknown;
  detect_status: string;
};

// Unwrap the {success, data} envelope returned by FastAPI
function extractData<T>(raw: { success: boolean; data: T; error?: string }): T {
  if (!raw.success) throw new Error(raw.error || "API error");
  return raw.data;
}

export const api = createApi({
  reducerPath: "api",
  baseQuery: fetchBaseQuery({ baseUrl: API_URL }),
  tagTypes: ["Action", "Patient", "Caregiver", "Org", "ChatHistory", "Schedule", "Assignments", "UpdateHistory", "SetupStatus"],
  endpoints: (builder) => ({
    // ── Actions ──────────────────────────────────────────────────────────────
    getActions: builder.query<Action[], { sort?: string } | void>({
      query: (args) => `/actions?sort=${args?.sort ?? "rank"}`,
      transformResponse: (raw: { success: boolean; data: Action[] }) => extractData(raw),
      providesTags: ["Action"],
    }),
    getAction: builder.query<Action, string>({
      query: (id) => `/actions/${id}`,
      transformResponse: (raw: { success: boolean; data: Action }) => extractData(raw),
      providesTags: (_result, _error, id) => [{ type: "Action", id }],
    }),
    patchAction: builder.mutation<Action, { id: string; body: Partial<Action> & { modification_instruction?: string; idempotency_key?: string } }>({
      query: ({ id, body }) => ({ url: `/actions/${id}`, method: "PATCH", body }),
      transformResponse: (raw: { success: boolean; data: Action }) => extractData(raw),
      invalidatesTags: ["Action"],
    }),
    approveAction: builder.mutation<Action, string>({
      query: (id) => ({ url: `/actions/${id}/approve`, method: "POST" }),
      transformResponse: (raw: { success: boolean; data: Action }) => extractData(raw),
      invalidatesTags: ["Action"],
    }),
    dismissAction: builder.mutation<Action, string>({
      query: (id) => ({ url: `/actions/${id}/dismiss`, method: "POST" }),
      transformResponse: (raw: { success: boolean; data: Action }) => extractData(raw),
      invalidatesTags: ["Action"],
    }),

    // ── Chat ─────────────────────────────────────────────────────────────────
    getChatHistory: builder.query<ChatMessage[], string>({
      query: (actionId) => `/actions/${actionId}/chat-history`,
      transformResponse: (raw: { success: boolean; data: ChatMessage[] }) => extractData(raw),
      providesTags: (_result, _error, id) => [{ type: "ChatHistory", id }],
    }),
    sendChatMessage: builder.mutation<ChatMessage, { actionId: string; message: string }>({
      query: ({ actionId, message }) => ({
        url: `/actions/${actionId}/chat`,
        method: "POST",
        body: { message },
      }),
      transformResponse: (raw: { success: boolean; data: ChatMessage }) => extractData(raw),
      invalidatesTags: (_result, _error, { actionId }) => [{ type: "ChatHistory", id: actionId }],
    }),

    // ── Patients ──────────────────────────────────────────────────────────────
    getPatients: builder.query<Patient[], void>({
      query: () => "/patients",
      transformResponse: (raw: { success: boolean; data: Patient[] }) => extractData(raw),
      providesTags: ["Patient"],
    }),
    getPatient: builder.query<Patient, string>({
      query: (id) => `/patients/${id}`,
      transformResponse: (raw: { success: boolean; data: Patient }) => extractData(raw),
      providesTags: (_result, _error, id) => [{ type: "Patient", id }],
    }),
    ingestText: builder.mutation<
      IngestResult,
      { content: string; patientId?: string; context?: string }
    >({
      query: ({ content, patientId, context }) => {
        const body: { content: string; patient_id?: string; context?: string } = { content };
        if (patientId) body.patient_id = patientId;
        if (context) body.context = context;
        return { url: "/ingest/text", method: "POST", body };
      },
      transformResponse: (raw: { success: boolean; data: IngestResult }) => extractData(raw),
      invalidatesTags: (result, _err, arg) =>
        arg.patientId
          ? (["Patient", "SetupStatus", "Action", { type: "Patient" as const, id: arg.patientId }, { type: "UpdateHistory" as const, id: arg.patientId }] as const)
          : (["Patient", "SetupStatus", "Action"] as const),
    }),
    ingestFile: builder.mutation<IngestResult, { file: File; patientId?: string; context?: string }>({
      query: ({ file, patientId, context }) => {
        const formData = new FormData();
        formData.append("file", file);
        if (patientId) formData.append("patient_id", patientId);
        if (context) formData.append("context", context);
        return { url: "/ingest/file", method: "POST", body: formData };
      },
      transformResponse: (raw: { success: boolean; data: IngestResult }) => extractData(raw),
      invalidatesTags: (result, _err, arg) =>
        arg.patientId
          ? (["Patient", "SetupStatus", "Action", { type: "Patient" as const, id: arg.patientId }, { type: "UpdateHistory" as const, id: arg.patientId }] as const)
          : (["Patient", "SetupStatus", "Action"] as const),
    }),
    submitPatientUpdate: builder.mutation<PatientUpdate, { patientId: string; content: string }>({
      query: ({ patientId, content }) => ({
        url: `/patients/${patientId}/update`,
        method: "POST",
        body: { content },
      }),
      transformResponse: (
        raw: { success: boolean; data: unknown },
        _meta: unknown,
        arg: { patientId: string; content: string }
      ) => {
        const data = extractData(raw) as {
          update_id: number;
          classification?: {
            proposed_changes?: Record<string, unknown>;
            domain?: string;
            summary?: string;
            fields_changed?: string[];
          };
        };
        const c = data.classification ?? {};
        return {
          update_id: String(data.update_id),
          patient_id: arg.patientId,
          submitted_at: new Date().toISOString(),
          status: "pending" as const,
          proposed_changes: c.proposed_changes,
          domain: c.domain,
          summary: c.summary,
        };
      },
      invalidatesTags: (_r, _e, { patientId }) => [{ type: "UpdateHistory" as const, id: patientId }],
    }),
    confirmPatientUpdate: builder.mutation<unknown, { patientId: string; updateId: string }>({
      query: ({ patientId, updateId }) => ({
        url: `/patients/${patientId}/update/${updateId}/confirm`,
        method: "POST",
      }),
      transformResponse: (raw: { success: boolean; data: unknown }) => extractData(raw),
      invalidatesTags: (_r, _e, { patientId }) => [
        "Patient",
        "Action",
        { type: "UpdateHistory" as const, id: patientId },
      ],
    }),
    getUpdateHistory: builder.query<PatientUpdate[], string>({
      query: (patientId) => `/patients/${patientId}/update-history`,
      transformResponse: (raw: { success: boolean; data: Record<string, unknown>[] }) => {
        const rows = extractData(raw);
        return rows.map((row) => {
          const id = row.id as number;
          const applied = Number(row.applied) === 1;
          const status: PatientUpdate["status"] = applied ? "confirmed" : "pending";
          const proposed = (row.proposed_changes ?? undefined) as Record<string, unknown> | undefined;
          const fromIngest = proposed?.ingest === true;
          return {
            update_id: String(id),
            patient_id: String(row.patient_id ?? ""),
            submitted_at: String(row.created_at ?? ""),
            status,
            summary: row.summary != null ? String(row.summary) : undefined,
            domain: row.domain != null ? String(row.domain) : undefined,
            proposed_changes: proposed,
            fromIngest,
          };
        });
      },
      providesTags: (_result, _error, id) => [{ type: "UpdateHistory", id }],
    }),

    // ── Caregivers ────────────────────────────────────────────────────────────
    createCaregiver: builder.mutation<Caregiver, CreateCaregiverBody>({
      query: (body) => ({ url: "/caregivers", method: "POST", body }),
      transformResponse: (raw: { success: boolean; data: Caregiver }) => extractData(raw),
      invalidatesTags: ["Caregiver", "SetupStatus"],
    }),
    getCaregivers: builder.query<Caregiver[], void>({
      query: () => "/caregivers",
      transformResponse: (raw: { success: boolean; data: Caregiver[] }) => extractData(raw),
      providesTags: ["Caregiver"],
    }),
    getCaregiverSchedule: builder.query<CaregiverScheduleSlot[], string>({
      query: (id) => `/caregivers/${id}/schedule`,
      transformResponse: (raw: { success: boolean; data: CaregiverScheduleSlot[] }) => extractData(raw),
      providesTags: (_result, _error, id) => [{ type: "Schedule", id }],
    }),
    getCaregiverAssignments: builder.query<CaregiverAssignment[], string>({
      query: (id) => `/caregivers/${id}/assignments`,
      transformResponse: (raw: { success: boolean; data: CaregiverAssignment[] }) => extractData(raw),
      providesTags: (_result, _error, id) => [{ type: "Assignments", id }],
    }),

    // ── Caregiver assignment ──────────────────────────────────────────────────
    getCaregiversAvailable: builder.query<Caregiver[], { start_time?: string; end_time?: string } | void>({
      query: (args) => {
        if (args?.start_time && args?.end_time) {
          return `/caregivers/available?start_time=${encodeURIComponent(args.start_time)}&end_time=${encodeURIComponent(args.end_time)}`;
        }
        return "/caregivers/available";
      },
      transformResponse: (raw: { success: boolean; data: Caregiver[] }) => extractData(raw),
      providesTags: ["Caregiver"],
    }),
    assignCaregiverToAction: builder.mutation<Action, { actionId: string; assigned_caregiver: string }>({
      query: ({ actionId, assigned_caregiver }) => ({
        url: `/actions/${actionId}`,
        method: "PATCH",
        body: { assigned_caregiver },
      }),
      transformResponse: (raw: { success: boolean; data: Action }) => extractData(raw),
      invalidatesTags: ["Action", "Caregiver"],
    }),

    // ── Setup ─────────────────────────────────────────────────────────────────
    getSetupStatus: builder.query<SetupStatus, void>({
      query: () => "/org/setup-status",
      transformResponse: (raw: { success: boolean; data: SetupStatus }) => extractData(raw),
      providesTags: ["SetupStatus"],
    }),

    // ── Org ───────────────────────────────────────────────────────────────────
    getOrg: builder.query<OrgProfile, void>({
      query: () => "/org",
      transformResponse: (raw: { success: boolean; data: OrgProfile }) => extractData(raw),
      providesTags: ["Org"],
    }),
    updateOrg: builder.mutation<OrgProfile, Partial<OrgProfile>>({
      query: (body) => ({ url: "/org", method: "PUT", body }),
      transformResponse: (raw: { success: boolean; data: OrgProfile }) => extractData(raw),
      invalidatesTags: ["Org", "SetupStatus"],
    }),

    // ── General Chat ──────────────────────────────────────────────────────────
    getGeneralChatHistory: builder.query<GeneralChatMessage[], string>({
      query: (sessionId) => `/chat/history?session_id=${encodeURIComponent(sessionId)}`,
      transformResponse: (raw: { success: boolean; data: GeneralChatMessage[] }) => extractData(raw),
      providesTags: (_r, _e, sessionId) => [{ type: "ChatHistory", id: `general-${sessionId}` }],
    }),
    sendGeneralChatMessage: builder.mutation<SendMessageResponse, { session_id?: string; message: string }>({
      query: (body) => ({ url: "/chat", method: "POST", body }),
      transformResponse: (raw: { success: boolean; data: SendMessageResponse }) => extractData(raw),
    }),
    approveDraft: builder.mutation<{ action_id: string }, string>({
      query: (draftId) => ({ url: `/chat/action/${draftId}/approve`, method: "POST" }),
      transformResponse: (raw: { success: boolean; data: { action_id: string } }) => extractData(raw),
      invalidatesTags: ["Action"],
    }),
    discardDraft: builder.mutation<{ status: string }, string>({
      query: (draftId) => ({ url: `/chat/action/${draftId}/discard`, method: "POST" }),
      transformResponse: (raw: { success: boolean; data: { status: string } }) => extractData(raw),
    }),
    modifyDraft: builder.mutation<{ reply: string; draft_action_id: string }, { draftId: string; feedback: string }>({
      query: ({ draftId, feedback }) => ({
        url: `/chat/action/${draftId}/modify`,
        method: "POST",
        body: { feedback },
      }),
      transformResponse: (raw: { success: boolean; data: { reply: string; draft_action_id: string } }) => extractData(raw),
    }),
  }),
});

export const {
  useGetSetupStatusQuery,
  useGetActionsQuery,
  useGetActionQuery,
  usePatchActionMutation,
  useApproveActionMutation,
  useDismissActionMutation,
  useGetChatHistoryQuery,
  useSendChatMessageMutation,
  useGetPatientsQuery,
  useGetPatientQuery,
  useIngestTextMutation,
  useIngestFileMutation,
  useSubmitPatientUpdateMutation,
  useConfirmPatientUpdateMutation,
  useGetUpdateHistoryQuery,
  useCreateCaregiverMutation,
  useGetCaregiversQuery,
  useGetCaregiverScheduleQuery,
  useGetCaregiverAssignmentsQuery,
  useGetCaregiversAvailableQuery,
  useAssignCaregiverToActionMutation,
  useGetOrgQuery,
  useUpdateOrgMutation,
  useGetGeneralChatHistoryQuery,
  useSendGeneralChatMessageMutation,
  useApproveDraftMutation,
  useDiscardDraftMutation,
  useModifyDraftMutation,
} = api;

// Store setup
import { configureStore } from "@reduxjs/toolkit";

export const store = configureStore({
  reducer: {
    [api.reducerPath]: api.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(api.middleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
