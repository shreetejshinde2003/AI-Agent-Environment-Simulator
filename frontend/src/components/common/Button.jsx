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
  ...rest
}) {
  return (
    <button type={type} className={`btn btn-${variant}`} onClick={onClick} {...rest}>
      {Icon && <Icon size={15} strokeWidth={2} />}
      <span>{children}</span>
    </button>
  );
}
