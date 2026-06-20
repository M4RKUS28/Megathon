import { createBrowserRouter } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { RoleRoute } from "@/components/RoleRoute";
import { LandingPage } from "@/pages/Landing";
import { AboutPage } from "@/pages/About";
import { SignInPage } from "@/pages/SignIn";
import { SignUpPage } from "@/pages/SignUp";
import { DashboardPage } from "@/pages/Dashboard";
import { FileManagerPage } from "@/pages/FileManager";
import { BrandingPage } from "@/pages/Branding";
import { PeoplePage } from "@/pages/People";
import { CompaniesPage } from "@/pages/Companies";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <LandingPage />,
  },
  {
    path: "/about",
    element: <AboutPage />,
  },
  {
    path: "/signin",
    element: <SignInPage />,
  },
  {
    path: "/signup",
    element: <SignUpPage />,
  },
  {
    element: (
      <ProtectedRoute>
        <Layout />
      </ProtectedRoute>
    ),
    children: [
      { path: "dashboard", element: <DashboardPage /> },
      { path: "files", element: <FileManagerPage /> },
      {
        path: "people",
        element: (
          <RoleRoute roles={["admin", "course_creator"]}>
            <PeoplePage />
          </RoleRoute>
        ),
      },
      {
        path: "branding",
        element: (
          <RoleRoute roles={["admin"]}>
            <BrandingPage />
          </RoleRoute>
        ),
      },
      {
        path: "companies",
        element: (
          <RoleRoute roles={["admin"]}>
            <CompaniesPage />
          </RoleRoute>
        ),
      },
    ],
  },
  {
    path: "/forbidden",
    element: (
      <div className="flex h-screen flex-col items-center justify-center gap-2">
        <h1 className="text-2xl font-bold">403 — Forbidden</h1>
        <p className="text-muted-foreground">You don't have permission to access this page.</p>
      </div>
    ),
  },
]);
