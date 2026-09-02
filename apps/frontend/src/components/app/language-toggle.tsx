import { Button } from "@/components/ui/button"
import { useI18n } from "@/lib/i18n"

export function LanguageToggle() {
  const { locale, setLocale } = useI18n()

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => setLocale(locale === "en" ? "es" : "en")}
      aria-label="Toggle language"
      className="font-mono uppercase"
    >
      {locale === "en" ? "ES" : "EN"}
    </Button>
  )
}
