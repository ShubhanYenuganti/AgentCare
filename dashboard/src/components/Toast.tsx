interface Props {
  message: string;
}

export default function Toast({ message }: Props) {
  return (
    <div
      style={{
        position: "fixed",
        bottom: "1.5rem",
        right: "1.5rem",
        backgroundColor: "#1f2937",
        color: "#fff",
        padding: "0.75rem 1.25rem",
        borderRadius: "8px",
        fontSize: "0.875rem",
        fontWeight: 500,
        zIndex: 200,
        boxShadow: "0 4px 16px rgba(0,0,0,0.25)",
        display: "flex",
        alignItems: "center",
        gap: "0.625rem",
      }}
    >
      <span
        style={{
          width: "10px",
          height: "10px",
          borderRadius: "50%",
          backgroundColor: "#60a5fa",
          flexShrink: 0,
          opacity: 0.9,
        }}
      />
      {message}
    </div>
  );
}
