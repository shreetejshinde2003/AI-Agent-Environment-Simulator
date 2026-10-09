import "./Button.css";

/**
 * Button — shared button styling for the whole app.
 * variant: "default" | "primary" | "danger" | "ghost"
 */
export default function Button({
  children,
  icon: Icon,
  variant = "default",
  onClick,
  type = "button",
  className = "",
  ...rest
}) {
  return (
    <button type={type} className={`btn btn-${variant}${className ? ` ${className}` : ""}`} onClick={onClick} {...rest}>
      {Icon && <Icon size={15} strokeWidth={2} aria-hidden="true" />}
      <span>{children}</span>
    </button>
  );
}
