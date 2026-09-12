import "./globals.css";
import "../styles/main.scss";
// A static asset terminates the graph rather than extending it, and a token
// module spells its concepts in camelCase. Both classes were invisible to
// this fixture until they were put in it.
import logo from "./assets/logo.svg";
import hero from "./assets/hero.png?url";
import { typography } from "./tokens/typography";
export default function Layout({ children }) { return children; }
