import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'

type StoryHeaderProps = {
  number: string
  label: string
  title: string
  children: ReactNode
}

function StoryHeader({ number, label, title, children }: StoryHeaderProps) {
  return <div className="story-header">
    <div className="story-index"><span>{number}</span><i /></div>
    <p className="story-kicker">{label}</p>
    <h2>{title}</h2>
    <p className="story-copy">{children}</p>
  </div>
}

function useLandingMotion() {
  const [scrollY, setScrollY] = useState(0)
  const [reducedMotion, setReducedMotion] = useState(false)

  useEffect(() => {
    const motionQuery = typeof window.matchMedia === 'function' ? window.matchMedia('(prefers-reduced-motion: reduce)') : null
    let frame: number | undefined
    const syncMotion = () => setReducedMotion(Boolean(motionQuery?.matches))
    const updateActiveSection = () => {
      const marker = window.innerHeight * 0.32
      const current = [...document.querySelectorAll<HTMLElement>('.marketing-site .story-section')].find((section) => {
        const rect = section.getBoundingClientRect()
        return rect.top <= marker && rect.bottom > marker
      })
      if (current?.id) {
        document.querySelectorAll<HTMLAnchorElement>('.marketing-nav-links a').forEach((link) => link.classList.toggle('active', link.getAttribute('href') === `#${current.id}`))
      }
    }
    const updateScroll = () => {
      if (frame !== undefined) return
      const schedule = (callback: FrameRequestCallback) => typeof window.requestAnimationFrame === 'function' ? window.requestAnimationFrame(callback) : window.setTimeout(callback, 0)
      frame = schedule(() => {
        frame = undefined
        setScrollY(window.scrollY)
        updateActiveSection()
        const total = Math.max(1, document.documentElement.scrollHeight - window.innerHeight)
        document.documentElement.style.setProperty('--story-progress', `${Math.min(100, Math.max(0, (window.scrollY / total) * 100))}%`)
        document.querySelector('.marketing-nav')?.classList.toggle('is-scrolled', window.scrollY > 24)
      })
    }
    syncMotion()
    updateActiveSection()
    const storySections = [...document.querySelectorAll<HTMLElement>('.marketing-site .story-section')]
    storySections.forEach((section) => section.classList.add('motion-ready'))
    let sectionObserver: IntersectionObserver | undefined
    if (typeof window.IntersectionObserver === 'function') {
      sectionObserver = new IntersectionObserver((entries) => entries.forEach((entry) => entry.target.classList.toggle('is-in-view', entry.isIntersecting)), { threshold: 0.14, rootMargin: '-10% 0px -8% 0px' })
      storySections.forEach((section) => sectionObserver?.observe(section))
    } else {
      storySections.forEach((section) => section.classList.add('is-in-view'))
    }
    const handleSmoothNavigation = (event: Event) => {
      const origin = event.target
      if (!(origin instanceof Element)) return
      const link = origin.closest<HTMLAnchorElement>('a[href^="#"]')
      if (!link || (!link.closest('.marketing-nav-links') && !link.classList.contains('scroll-cue') && !link.classList.contains('hero-explore-overlay'))) return
      const target = document.getElementById(link.hash.slice(1))
      if (!target) return
      event.preventDefault()
      target.scrollIntoView?.({ behavior: motionQuery?.matches ? 'auto' : 'smooth', block: 'start' })
    }
    const updateProgress = () => {
      const total = Math.max(1, document.documentElement.scrollHeight - window.innerHeight)
      document.documentElement.style.setProperty('--story-progress', `${Math.min(100, Math.max(0, (window.scrollY / total) * 100))}%`)
      document.querySelector('.marketing-nav')?.classList.toggle('is-scrolled', window.scrollY > 24)
    }
    document.addEventListener('click', handleSmoothNavigation)
    updateProgress()
    window.addEventListener('scroll', updateScroll, { passive: true })
    motionQuery?.addEventListener?.('change', syncMotion)
    return () => {
      window.removeEventListener('scroll', updateScroll)
      document.removeEventListener('click', handleSmoothNavigation)
      motionQuery?.removeEventListener?.('change', syncMotion)
      sectionObserver?.disconnect()
      if (frame !== undefined) {
        window.cancelAnimationFrame?.(frame)
        window.clearTimeout(frame)
      }
    }
  }, [])

  return { scrollY, reducedMotion }
}

function ParallaxLayer({ depth, xDepth = 0, scrollY, reducedMotion, className = '', style, children }: { depth: number; xDepth?: number; scrollY: number; reducedMotion: boolean; className?: string; style?: React.CSSProperties; children: ReactNode }) {
  const shiftY = reducedMotion ? 0 : Math.min(48, Math.max(-48, scrollY * depth))
  const shiftX = reducedMotion ? 0 : Math.min(24, Math.max(-24, scrollY * xDepth))
  return <div className="parallax-layer" style={{ ...style, '--parallax-x': `${shiftX}px`, '--parallax-y': `${shiftY}px` } as React.CSSProperties}><div className={className}>{children}</div></div>
}

function sectionProgress(id: string, reducedMotion: boolean) {
  if (reducedMotion || typeof window === 'undefined') return 1
  const section = document.getElementById(id)
  if (!section) return 0
  const rect = section.getBoundingClientRect()
  return Math.min(1, Math.max(0, (window.innerHeight - rect.top) / (window.innerHeight + rect.height)))
}

function DocumentCard({ label, tone = '', handwritten = false }: { label: string; tone?: string; handwritten?: boolean }) {
  return <div className={`source-card ${tone} ${handwritten ? 'handwritten' : ''}`}>
    <span className="source-card-label">{label}</span>
    <div className="source-card-lines"><i /><i /><i /><i /></div>
    {handwritten && <span className="source-script">notes / 7.4</span>}
  </div>
}

function HeroDocuments({ scrollY, reducedMotion }: { scrollY: number; reducedMotion: boolean }) {
  const memoryShift = reducedMotion ? 0 : Math.min(18, scrollY * 0.012)
  const languageShift = reducedMotion ? 0 : Math.min(36, scrollY * 0.05)
  return <div className="hero-visual" style={{ '--memory-shift': `${memoryShift}px`, '--language-shift': `${languageShift}px` } as React.CSSProperties} aria-label="Clinical document sources becoming one patient story">
    <a href="#problem" className="hero-explore-overlay">Explore the story <span>↓</span></a>
    <div className="hero-glow" />
    <ParallaxLayer depth={0.012} xDepth={0.004} scrollY={scrollY} reducedMotion={reducedMotion} className="hero-ring hero-ring-one"><span /></ParallaxLayer>
    <ParallaxLayer depth={0.018} xDepth={-0.006} scrollY={scrollY} reducedMotion={reducedMotion} className="hero-ring hero-ring-two"><span /></ParallaxLayer>
    <ParallaxLayer depth={0.03} xDepth={0.015} scrollY={scrollY} reducedMotion={reducedMotion} className="hero-source hero-source-one"><DocumentCard label="Prescription" tone="teal-card" /></ParallaxLayer>
    <ParallaxLayer depth={0.024} xDepth={-0.012} scrollY={scrollY} reducedMotion={reducedMotion} className="hero-source hero-source-two"><DocumentCard label="Lab report" tone="blue-card" /></ParallaxLayer>
    <ParallaxLayer depth={0.042} xDepth={0.02} scrollY={scrollY} reducedMotion={reducedMotion} className="hero-source hero-source-three"><DocumentCard label="Handwritten note" tone="amber-card" handwritten /></ParallaxLayer>
    <ParallaxLayer depth={0.026} xDepth={-0.009} scrollY={scrollY} reducedMotion={reducedMotion} className="hero-source hero-source-four"><DocumentCard label="Previous visit" tone="paper-card" /></ParallaxLayer>
    <div className="hero-memory-card"><div className="memory-card-mark">✦</div><p className="source-card-label">PATIENT MEMORY</p><strong>One evolving story</strong><span>Traceable · physician controlled</span><div className="memory-card-path"><i /><i /><i /><i /></div></div>
    <div className="hero-language-tag">हिन्दी <span>·</span> বাংলা <span>·</span> தமிழ்</div>
  </div>
}

function SourceOrbit({ scrollY, reducedMotion, progress }: { scrollY: number; reducedMotion: boolean; progress?: number }) {
  const convergence = progress ?? sectionProgress('connect', reducedMotion)
  return <div className="source-orbit" style={{ '--converge': convergence } as React.CSSProperties} aria-label="Clinical source fragments converging into patient memory">
    <ParallaxLayer depth={0.04} scrollY={scrollY} reducedMotion={reducedMotion} className="orbit-fragment orbit-prescription"><DocumentCard label="Prescription" tone="teal-card" /></ParallaxLayer>
    <ParallaxLayer depth={0.06} scrollY={scrollY} reducedMotion={reducedMotion} className="orbit-fragment orbit-lab"><DocumentCard label="Lab report" tone="blue-card" /></ParallaxLayer>
    <ParallaxLayer depth={0.03} scrollY={scrollY} reducedMotion={reducedMotion} className="orbit-fragment orbit-visit"><DocumentCard label="Visit note" /></ParallaxLayer>
    <ParallaxLayer depth={0.08} scrollY={scrollY} reducedMotion={reducedMotion} className="orbit-fragment orbit-hand"><DocumentCard label="Handwritten" tone="amber-card" handwritten /></ParallaxLayer>
    <ParallaxLayer depth={0.05} scrollY={scrollY} reducedMotion={reducedMotion} className="orbit-fragment orbit-language"><span className="language-chip">தமிழ்</span></ParallaxLayer>
    <div className="orbit-center"><div className="orbit-center-icon">✦</div><strong>Patient<br />Memory</strong><span>connected context</span></div>
  </div>
}

function LanguageMap() {
  return <div className="language-composition">
    <div className="india-map-art"><img src="/assets/india-map.png" alt="" className="india-map-image" /></div>
  </div>
}

function MemoryTimeline({ scrollY, reducedMotion, progress }: { scrollY: number; reducedMotion: boolean; progress?: number }) {
  const memoryProgress = progress ?? sectionProgress('memory', reducedMotion)
  const items = [
    ['2019', 'Hypertension', 'visit note', 'verified'],
    ['2022', 'Metformin', 'prescription', 'verified'],
    ['2025', 'HbA1c · 7.4%', 'lab report', 'review'],
    ['TODAY', 'Current consultation', 'physician review', 'current'],
  ]
  return <div className="memory-visual" style={{ '--memory-progress': memoryProgress } as React.CSSProperties}>
    <ParallaxLayer depth={0.035} scrollY={scrollY} reducedMotion={reducedMotion} className="memory-visual-backdrop"><span>LONGITUDINAL MEMORY</span></ParallaxLayer>
    <div className="memory-timeline-line" />
    {items.map(([year, title, source, tone], index) => <div className={`memory-event memory-event-${tone}`} key={title} style={{ '--event-index': index } as React.CSSProperties}><span className="memory-event-year">{year}</span><span className="memory-event-node" /><div><strong>{title}</strong><small>{source}</small></div></div>)}
    <div className="memory-trace-card"><span>TRACEABLE SOURCE</span><strong>HbA1c 7.4%</strong><small>Lab_Report_2025.pdf · page 2</small><b>↗</b></div>
  </div>
}

function ReviewFlow({ progress }: { progress?: number }) {
  const flowProgress = progress ?? sectionProgress('physician-loop', false)
  const steps = [['AI extraction', 'Information', 'information'], ['Confidence', '92%', 'verified'], ['Review', 'Needed', 'review'], ['Physician approval', 'Final authority', 'verified']]
  return <div className="review-flow" aria-label="AI extraction to physician approval flow">{steps.map(([label, value, tone], index) => { const stepProgress = Math.min(1, Math.max(0, flowProgress * 1.65 - index * 0.24)); return <div className="review-flow-step" style={{ '--step-progress': stepProgress, opacity: .34 + stepProgress * .66, transform: `translate3d(0, ${(1 - stepProgress) * 15}px, 0)` } as React.CSSProperties} key={label}><div className={`review-flow-node ${tone}`}><span>{index + 1}</span></div><p>{label}</p><strong>{value}</strong>{index < steps.length - 1 && <i />}</div> })}</div>
}

function DecisionFlow() {
  return <div className="decision-visual"><div className="decision-input memory-input"><span>✦</span><div><small>LONGITUDINAL CONTEXT</small><strong>Patient Memory</strong></div></div><div className="decision-plus">+</div><div className="decision-input finding-input"><span>＋</span><div><small>LIVE ENCOUNTER</small><strong>Today's findings</strong></div></div><div className="decision-arrow">↓</div><div className="decision-output"><span className="output-spark">✦</span><div><small>PHYSICIAN-REVIEWED</small><strong>Relevant context</strong><p>Clinical draft</p></div><b>→</b></div></div>
}

export function LandingPage() {
  const { scrollY, reducedMotion } = useLandingMotion()

  return <div className={`marketing-site ${reducedMotion ? 'motion-reduced' : ''}`}>
    <header className="marketing-nav"><Link to="/" className="marketing-brand" aria-label="MedFlowAI home"><span className="marketing-brand-mark">✦</span><span>MedFlow<span>AI</span></span></Link><nav className="marketing-nav-links" aria-label="Public site"><a href="#story">The story</a><a href="#memory">Patient memory</a><a href="#physician-loop">Physician in the loop</a></nav><div className="marketing-nav-actions"><Link to="/login" className="nav-signin">Sign in</Link><Link to="/signup" className="small-cta">Get started <span>→</span></Link></div></header>
    <main>
      <section className="story-section hero-section" id="story"><div className="section-inner hero-inner"><div className="hero-copy"><p className="marketing-eyebrow">CLINICAL INTELLIGENCE FOR PHYSICIANS</p><h1>A patient's history is more than a <em>document.</em></h1><p className="hero-supporting">MedFlowAI brings clinical information together, helps physicians understand what matters, and keeps the physician in control.</p><div className="hero-actions"><Link to="/signup" className="primary-cta">Get started <span>→</span></Link><Link to="/login" className="secondary-cta">Sign in</Link></div><div className="hero-note"><span className="live-pulse" /> Built for connected, traceable clinical information</div></div><HeroDocuments scrollY={scrollY} reducedMotion={reducedMotion} /></div><a href="#problem" className="scroll-cue" aria-label="Scroll to the story"><span>Scroll to explore</span><i>↓</i></a></section>

      <section className="story-section problem-section" id="problem"><div className="section-inner split-story"><StoryHeader number="01" label="THE PROBLEM" title="The story exists. It's just scattered.">Important clinical information can live across reports, prescriptions, visits, handwritten notes, languages, and document formats.</StoryHeader><div className="scatter-visual"><div className="scatter-label">ONE PATIENT / MANY FRAGMENTS</div><ParallaxLayer depth={0.03} scrollY={scrollY} reducedMotion={reducedMotion} className="scatter-item scatter-a"><DocumentCard label="Previous visit" /></ParallaxLayer><ParallaxLayer depth={0.06} scrollY={scrollY} reducedMotion={reducedMotion} className="scatter-item scatter-b"><DocumentCard label="Prescription" tone="teal-card" /></ParallaxLayer><ParallaxLayer depth={0.04} scrollY={scrollY} reducedMotion={reducedMotion} className="scatter-item scatter-c"><DocumentCard label="Lab report" tone="blue-card" /></ParallaxLayer><ParallaxLayer depth={0.08} scrollY={scrollY} reducedMotion={reducedMotion} className="scatter-item scatter-d"><DocumentCard label="Handwritten note" tone="amber-card" handwritten /></ParallaxLayer><div className="scatter-dot scatter-dot-a" /><div className="scatter-dot scatter-dot-b" /><div className="scatter-dot scatter-dot-c" /></div></div></section>

      <section className="story-section accessibility-section" id="accessibility"><div className="section-inner split-story reverse-mobile"><div className="section-visual"><LanguageMap /></div><StoryHeader number="02" label="ACCESSIBILITY ACROSS INDIA" title="From many languages. Many formats. One patient story.">Designed to make clinical information more accessible across India's diverse languages and document formats.</StoryHeader></div></section>

      <section className="story-section connect-section" id="connect"><div className="section-inner split-story"><StoryHeader number="03" label="MEDFLOW CONNECTS THE PIECES" title="MedFlow connects the pieces.">Extract clinical information. Understand its meaning. Preserve its source. Connect it to the patient's history.</StoryHeader><SourceOrbit scrollY={scrollY} reducedMotion={reducedMotion} /></div></section>

      <section className="story-section memory-section" id="memory"><div className="section-inner split-story reverse-mobile"><div className="section-visual"><MemoryTimeline scrollY={scrollY} reducedMotion={reducedMotion} /></div><StoryHeader number="04" label="PATIENT MEMORY ENGINE" title="One patient. One evolving memory.">The Patient Memory Engine combines relevant history from multiple clinical sources while preserving where each fact came from.</StoryHeader></div></section>

      <section className="story-section physician-section" id="physician-loop"><div className="section-inner centered-story"><StoryHeader number="05" label="PHYSICIAN IN THE LOOP" title="AI can connect the story. The physician decides what belongs in it.">AI assists; the physician remains final authority.</StoryHeader><ReviewFlow /><div className="semantic-legend"><span><i className="legend-dot verified" /> Verified</span><span><i className="legend-dot review" /> Review</span><span><i className="legend-dot high-risk" /> High Risk</span><span><i className="legend-dot information" /> Information</span></div></div></section>

      <section className="story-section decision-section" id="decision"><div className="section-inner split-story"><StoryHeader number="06" label="FROM MEMORY TO TODAY'S DECISION" title="From history to today's decision.">Relevant patient history and today's findings come together to support physician-reviewed clinical documentation.</StoryHeader><DecisionFlow /></div></section>

      <section className="final-cta-section"><div className="final-cta-orbit final-orbit-a" /><div className="final-cta-orbit final-orbit-b" /><div className="final-cta-inner"><p className="marketing-eyebrow">A BETTER CLINICAL STARTING POINT</p><h2>Bring the patient's story together.</h2><p>Enter a physician-controlled clinical workspace built around connected, traceable patient information.</p><div className="hero-actions"><Link to="/signup" className="primary-cta">Create your account <span>→</span></Link><Link to="/login" className="final-signin">Sign in</Link></div></div></section>
    </main>
    <footer className="marketing-footer"><Link to="/" className="marketing-brand"><span className="marketing-brand-mark">✦</span><span>MedFlow<span>AI</span></span></Link><span>Clinical Intelligence</span><nav aria-label="Footer"><Link to="/login">Sign in</Link><Link to="/signup">Create account</Link></nav></footer>
  </div>
}
