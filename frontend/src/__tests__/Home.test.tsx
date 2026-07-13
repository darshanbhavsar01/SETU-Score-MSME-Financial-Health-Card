import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Home } from "../pages/Home";

describe("Home", () => {
  it("renders the problem, solution, and technical sections", () => {
    render(<Home onLaunch={() => {}} />);
    expect(screen.getByText(/Millions of MSMEs are invisible to credit/)).toBeInTheDocument();
    expect(screen.getByText(/One explainable score, four alternate data sources/)).toBeInTheDocument();
    expect(screen.getByText(/Explainable-by-design, AI-augmented/)).toBeInTheDocument();
    expect(screen.getByText("Why lenders choose it")).toBeInTheDocument();
  });

  it("calls onLaunch when a console CTA is clicked", () => {
    const onLaunch = vi.fn();
    render(<Home onLaunch={onLaunch} />);
    const [heroCta] = screen.getAllByText(/Open the Officer Console/);
    fireEvent.click(heroCta);
    expect(onLaunch).toHaveBeenCalledOnce();
  });
});
