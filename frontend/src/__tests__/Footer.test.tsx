import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Footer } from "../components/Footer";

describe("Footer", () => {
  it("credits the builder and links to the correct LinkedIn profile", () => {
    render(<Footer />);
    const link = screen.getByRole("link", { name: "Darshan Bhavsar" });
    expect(link).toHaveAttribute("href", "https://www.linkedin.com/in/darshan01/");
  });
});
