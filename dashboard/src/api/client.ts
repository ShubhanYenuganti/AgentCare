import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import type {
  Action,
  Caregiver,
  CaregiverAssignment,
  CaregiverScheduleSlot,
  ChatMessage,
  CreateCaregiverBody,
  OrgProfile,
  Patient,
  PatientUpdate,
  SchedulingOption,
  SetupStatus,
} from "../types";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

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
    ingestText: builder.mutation<Patient, string>({
      query: (text) => ({ url: "/ingest/text", method: "POST", body: { text } }),
      transformResponse: (raw: { success: boolean; data: Patient }) => extractData(raw),
      invalidatesTags: ["Patient", "SetupStatus"],
    }),
    ingestFile: builder.mutation<Patient, FormData>({
      query: (formData) => ({ url: "/ingest/file", method: "POST", body: formData }),
      transformResponse: (raw: { success: boolean; data: Patient }) => extractData(raw),
      invalidatesTags: ["Patient", "SetupStatus"],
    }),
    submitPatientUpdate: builder.mutation<PatientUpdate, { patientId: string; update_text: string }>({
      query: ({ patientId, update_text }) => ({
        url: `/patients/${patientId}/update`,
        method: "POST",
        body: { update_text },
      }),
      transformResponse: (raw: { success: boolean; data: PatientUpdate }) => extractData(raw),
    }),
    confirmPatientUpdate: builder.mutation<PatientUpdate, { patientId: string; updateId: string }>({
      query: ({ patientId, updateId }) => ({
        url: `/patients/${patientId}/update/${updateId}/confirm`,
        method: "POST",
      }),
      transformResponse: (raw: { success: boolean; data: PatientUpdate }) => extractData(raw),
      invalidatesTags: ["Patient", "Action"],
    }),
    getUpdateHistory: builder.query<PatientUpdate[], string>({
      query: (patientId) => `/patients/${patientId}/update-history`,
      transformResponse: (raw: { success: boolean; data: PatientUpdate[] }) => extractData(raw),
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
