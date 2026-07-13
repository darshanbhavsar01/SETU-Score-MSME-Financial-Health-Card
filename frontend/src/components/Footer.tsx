// Site-wide footer: builder credit + synthetic-data disclaimer, present on every page.

const LINKEDIN_URL = "https://www.linkedin.com/in/darshan01/";
const GITHUB_URL = "https://github.com/darshanbhavsar01/SETU-Score-MSME-Financial-Health-Card";

export function Footer() {
  return (
    <footer
      style={{
        borderTop: "1px solid var(--border)",
        marginTop: 48,
        padding: "24px 20px 32px",
      }}
    >
      <div
        style={{
          maxWidth: 1100,
          margin: "0 auto",
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          fontSize: 13,
        }}
      >
        <span className="muted">
          Built by{" "}
          <a
            href={LINKEDIN_URL}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: "var(--text-primary)", fontWeight: 600, textDecoration: "none" }}
          >
            Darshan Bhavsar
          </a>
        </span>

        <span style={{ display: "inline-flex", gap: 16, alignItems: "center" }}>
          <a href={LINKEDIN_URL} target="_blank" rel="noopener noreferrer" className="muted">
            LinkedIn
          </a>
          <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" className="muted">
            Source on GitHub
          </a>
          <span className="muted">Synthetic data · Hackathon POC</span>
        </span>
      </div>
    </footer>
  );
}
