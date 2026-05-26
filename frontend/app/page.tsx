'use client'

import Link from 'next/link'
import {
  ArrowRight,
  ArrowUpRight,
  BrainCircuit,
  GitBranch,
  MessagesSquare,
  Sparkles,
  Workflow,
  Bot,
  Briefcase,
  HelpCircle,
  FileText,
  Upload,
  ScrollText,
  Layers,
} from 'lucide-react'
import { motion, useReducedMotion, type Variants } from 'framer-motion'

import SiteHeader from '@/components/site/site-header'
import SiteFooter from '@/components/site/site-footer'
import QuorumMark from '@/components/site/quorum-mark'

// ============================================
// Animation primitives
// ============================================

const fadeUp: Variants = {
  hidden: { opacity: 0, y: 24 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] },
  },
}

const fadeIn: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { duration: 0.5, ease: 'easeOut' },
  },
}

const staggerContainer: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.05 },
  },
}

const staggerItem: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] },
  },
}

// ============================================
// Capabilities — 6 cards framed around the RFC review use case
// ============================================
const capabilities = [
  {
    title: 'Drop in the design doc',
    description:
      'Upload the RFC as PDF, Markdown, or plain text. Quorum extracts the content and grounds the review in your actual proposal, not a paraphrase.',
    icon: Upload,
  },
  {
    title: 'Standing reviewer panel',
    description:
      'A fixed roster — principal engineer, SRE, security, cost, product, tech lead, skeptic — each with a non-overlapping mandate, so every RFC gets the same disciplined coverage.',
    icon: MessagesSquare,
  },
  {
    title: 'Typed RFC knowledge graph',
    description:
      'Decisions, alternatives, trade-offs, constraints, components, failure modes, and stakeholders are extracted into a deterministic schema — auditable, no LLM-invented ontology.',
    icon: BrainCircuit,
  },
  {
    title: 'Live graph view',
    description:
      'Force-directed d3 visualization of the RFC graph. Drag nodes, toggle edge labels, click to inspect a candidate alternative and the trade-offs the panel pinned to it.',
    icon: GitBranch,
  },
  {
    title: 'Structured debate',
    description:
      'Each reviewer argues from its mandate over rounds — security on threat surface, SRE on blast radius, cost on TCO. Dissents are preserved verbatim, not laundered into consensus.',
    icon: Layers,
  },
  {
    title: 'Markdown ADR output',
    description:
      'A fixed Architecture Decision Record: context, drivers, alternatives considered, recommended decision, why-not each alternative, dissents, consequences, follow-ups. Download as .md.',
    icon: ScrollText,
  },
]

// ============================================
// 7-stage pipeline (engineering RFC framing)
// ============================================
const pipelineStages = [
  {
    n: '01',
    title: 'Apply RFC ontology',
    description:
      'Fixed deterministic schema — Decision, Alternative, Tradeoff, Constraint, Component, FailureMode, Reviewer. No LLM-invented types.',
  },
  {
    n: '02',
    title: 'Build the RFC graph',
    description:
      'Extracts decisions, alternatives, trade-offs, constraints, and stakeholders from the brief and uploaded design docs.',
  },
  {
    n: '03',
    title: 'Convene the reviewer panel',
    description:
      'Seven-seat standing panel deterministically instantiated — same coverage every RFC, no LLM persona drift.',
  },
  {
    n: '04',
    title: 'Calibrate the debate',
    description:
      'Per-reviewer activity profile so the security seat speaks on threats, cost speaks on TCO — each on its own mandate.',
  },
  {
    n: '05',
    title: 'Open the review',
    description:
      'Seed each reviewer with the decision under consideration and the trade-offs the brief exposes.',
  },
  {
    n: '06',
    title: 'Run the deliberation',
    description:
      'Round-by-round structured debate. The skeptic attacks the leading option; dissents are captured verbatim.',
  },
  {
    n: '07',
    title: 'Emit the ADR',
    description:
      'Markdown Architecture Decision Record — recommended decision, alternatives considered, why-not each, dissents, consequences, follow-ups.',
  },
]

// ============================================
// Use cases
// ============================================
const useCases = [
  {
    icon: GitBranch,
    label: 'Database & storage',
    title: 'Adopt PostgreSQL over MongoDB?',
    body:
      'Drop in the design doc. The panel reviews it the way an RFC review should be done — principal eng on architectural fit, SRE on operational risk, security on threat surface, cost on TCO, product on user intent, tech lead on team velocity, skeptic on anchoring. Output: a Markdown ADR with the recommended decision, why not each alternative, and the dissents preserved verbatim.',
  },
  {
    icon: Workflow,
    label: 'Service decomposition',
    title: 'Split the monolith or harden the seam?',
    body:
      'Carving a service out of a monolith has a dozen second-order effects. The panel surfaces them up front — blast radius, deploy gating, on-call burden, PCI scope, hidden coupling — so the ADR captures the alternatives you considered, not just the one you shipped.',
  },
  {
    icon: Layers,
    label: 'Build vs. buy',
    title: 'Self-host the observability stack or pay Datadog?',
    body:
      'Cost and operational complexity argue against each other; security has its own constraints; the team you have today is not the team you have at 10x. The panel makes those forces explicit so the call is reproducible.',
  },
  {
    icon: BrainCircuit,
    label: 'Identity & platform',
    title: 'Pick a single identity provider across three apps.',
    body:
      'Okta vs. self-hosted Keycloak vs. AWS Cognito. SOC 2 controls, an existing SAML integration, and a six-month rollout window. The panel weighs the trade-offs and emits the ADR you would have written from scratch — with the alternatives you rejected, and why, captured for the next person.',
  },
]

// ============================================
// FAQ
// ============================================
const faqs = [
  {
    q: 'How is this different from asking one LLM to "review my RFC from multiple perspectives"?',
    a: 'A single LLM playing roles converges on its own bias — every "perspective" ends up sounding the same. Quorum gives each reviewer its own system prompt and a non-overlapping mandate (security cares about threat surface, SRE cares about blast radius, cost about TCO), runs them through structured rounds, and preserves dissents verbatim. The disagreements are the point.',
  },
  {
    q: 'Is the reviewer panel hardcoded? Can I change it?',
    a: 'The default RFC reviewer roster has seven seats — Principal Engineer, Reliability, Security, Cost, Product, Tech Lead, Skeptic — chosen so the trade-off coverage is the same on every RFC. The roster lives in one Python file (engineering_rfc.py) so you can fork it for your team\'s seats. Domains are a small extension point on purpose.',
  },
  {
    q: 'What does the ADR look like?',
    a: 'A fixed 8-section Markdown document: Context, Decision drivers, Alternatives considered, Recommended decision, Why not the alternatives, Dissents, Consequences and risks, Follow-ups and open questions. Direct quotes from reviewers appear as blockquotes. A Provenance footer records who generated it and when. Download as .md.',
  },
  {
    q: 'What kind of files can I upload?',
    a: 'PDF, Markdown, and plain text — your existing design docs, RFCs, or system snapshots. Up to 5 files per project, 8 MB each. Text is extracted with pypdf and grounded in the RFC graph so the deliberation references your actual proposal.',
  },
  {
    q: 'Do I need an OpenAI key?',
    a: 'No. Quorum supports Google Gemini (free tier — great for evaluating), Anthropic Claude (paid), and Azure AI Foundry (Kimi K2.5 and others). The LLM layer is provider-agnostic — switching is one env var.',
  },
  {
    q: 'How big an RFC can it review?',
    a: 'The in-memory graph builder is bounded to ~40 nodes and ~60 edges, which fits any single design doc comfortably. For a multi-RFC architecture review, run them as separate projects and link the ADRs.',
  },
  {
    q: 'Can I still use it for non-engineering decisions?',
    a: 'Yes. A `general` mode is registered as a fallback domain — the LLM designs a stakeholder panel for any brief (strategy, policy, vendor selection). Pass `"domain": "general"` when creating the project. The platform is leaning into engineering RFC review as the flagship, but the engine stays domain-agnostic.',
  },
  {
    q: 'What happens if the LLM hits a content filter?',
    a: 'Quorum catches the content filter error, logs it to the system dashboard, and the affected reviewer skips its turn cleanly. The deliberation continues with the rest of the panel. You will see exactly which reviewer was blocked and why.',
  },
]

// ============================================
// Stack strip
// ============================================
const integrations = [
  'Google Gemini',
  'Azure / Kimi K2.5',
  'Claude API',
  'Next.js 14',
  'FastAPI',
  'd3-force',
  'pypdf',
  'NetworkX',
]

// ============================================
// Main page
// ============================================
export default function LandingPage() {
  const reduceMotion = useReducedMotion()
  // When the user has prefers-reduced-motion, drop straight to visible
  // (no transitions, no scroll triggers).
  const initialState = reduceMotion ? 'visible' : 'hidden'

  return (
    <main className="min-h-screen flex flex-col bg-[var(--bg)]">
      <SiteHeader />

      {/* ============================================
          Hero
          ============================================ */}
      <section className="relative overflow-hidden">
        <div className="container-2xl pt-16 pb-24 lg:pt-24 lg:pb-32">
          <div className="grid lg:grid-cols-[1.2fr_1fr] gap-12 lg:gap-16 items-center">
            <motion.div
              initial={initialState}
              animate="visible"
              variants={staggerContainer}
            >
              <motion.div
                variants={staggerItem}
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[var(--brand-soft)] border border-[var(--brand)]/20"
              >
                <Sparkles className="h-3.5 w-3.5 text-[var(--brand)]" />
                <span className="text-xs font-medium text-[var(--brand)]">
                  Multi-agent RFC review for engineering teams
                </span>
              </motion.div>

              <motion.h1
                variants={staggerItem}
                className="h1 mt-6 text-[var(--ink)]"
              >
                Drop in an RFC. Get a{' '}
                <span className="brand-pill">real ADR</span> back.
              </motion.h1>

              <motion.p
                variants={staggerItem}
                className="mt-6 max-w-xl text-lg leading-relaxed text-[var(--muted)]"
              >
                Quorum convenes a standing reviewer panel —{' '}
                <span className="text-[var(--ink)]">principal eng, SRE,
                security, cost, product, tech lead, skeptic</span> — and runs
                a structured deliberation on your design doc. Output: a
                Markdown{' '}
                <span className="text-[var(--ink)]">Architecture Decision
                Record</span> with the recommended decision, alternatives
                considered, dissents preserved verbatim, and the consequences
                the panel expects in 3, 6, and 12 months. Self-hosted, with
                the LLM provider of your choice.
              </motion.p>

              <motion.div
                variants={staggerItem}
                className="mt-8 flex flex-wrap gap-3"
              >
                <Link href="/workspace" className="btn btn-primary btn-lg">
                  Launch workspace
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <Link href="/docs" className="btn btn-ghost btn-lg">
                  Read the docs
                  <Workflow className="h-4 w-4" />
                </Link>
              </motion.div>

              <motion.div
                variants={staggerItem}
                className="mt-12 grid grid-cols-3 gap-6 max-w-md"
              >
                <div>
                  <p className="font-display text-3xl font-medium text-[var(--ink)]">7</p>
                  <p className="mt-1 text-xs text-[var(--muted)]">Reviewer seats</p>
                </div>
                <div>
                  <p className="font-display text-3xl font-medium text-[var(--ink)]">8</p>
                  <p className="mt-1 text-xs text-[var(--muted)]">ADR sections</p>
                </div>
                <div>
                  <p className="font-display text-3xl font-medium text-[var(--ink)]">100%</p>
                  <p className="mt-1 text-xs text-[var(--muted)]">Self-hostable</p>
                </div>
              </motion.div>
            </motion.div>

            <motion.div
              initial={reduceMotion ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 0.95, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
            >
              <HeroPreview />
            </motion.div>
          </div>
        </div>

        <div className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-[var(--bg-soft)] to-transparent pointer-events-none" />
      </section>

      {/* ============================================
          Stack strip
          ============================================ */}
      <RevealSection className="border-y border-[var(--line)] bg-[var(--bg-soft)]">
        <div className="container-2xl py-12">
          <p className="label-mono text-center mb-8">Powered by an open stack</p>
          <motion.div
            variants={staggerContainer}
            initial={initialState}
            whileInView="visible"
            viewport={{ once: true, amount: 0.4 }}
            className="flex flex-wrap items-center justify-center gap-x-10 gap-y-4"
          >
            {integrations.map((name) => (
              <motion.span
                key={name}
                variants={staggerItem}
                className="text-sm font-medium text-[var(--muted)] hover:text-[var(--ink)] transition-colors"
              >
                {name}
              </motion.span>
            ))}
          </motion.div>
        </div>
      </RevealSection>

      {/* ============================================
          Capabilities
          ============================================ */}
      <RevealSection id="capabilities" className="section">
        <div className="container-2xl">
          <SectionHeading
            label="Capabilities"
            heading={
              <>
                The way an RFC should be{' '}
                <span className="brand-pill">reviewed</span>.
              </>
            }
            description="Every RFC gets the same disciplined coverage — same seven seats, same eight-section ADR, dissents preserved verbatim. Built to be self-hosted with the LLM provider of your choice."
          />

          <motion.div
            variants={staggerContainer}
            initial={initialState}
            whileInView="visible"
            viewport={{ once: true, amount: 0.15 }}
            className="mt-14 grid gap-px bg-[var(--line)] border border-[var(--line)] rounded-lg overflow-hidden md:grid-cols-2 lg:grid-cols-3"
          >
            {capabilities.map((item) => {
              const Icon = item.icon
              return (
                <motion.div
                  key={item.title}
                  variants={staggerItem}
                  className="bg-[var(--card)] p-8 transition-colors hover:bg-[var(--brand-tint)] group"
                >
                  <div className="inline-flex h-10 w-10 items-center justify-center rounded-md bg-[var(--bg-soft)] group-hover:bg-[var(--brand-soft)] transition-colors">
                    <Icon className="h-5 w-5 text-[var(--ink)] group-hover:text-[var(--brand)] transition-colors" />
                  </div>
                  <h3 className="mt-5 font-display text-xl font-medium tracking-tight text-[var(--ink)]">
                    {item.title}
                  </h3>
                  <p className="mt-3 text-sm leading-relaxed text-[var(--muted)]">
                    {item.description}
                  </p>
                </motion.div>
              )
            })}
          </motion.div>
        </div>
      </RevealSection>

      {/* ============================================
          Pipeline — 7 numbered cards
          ============================================ */}
      <RevealSection
        id="workflow"
        className="section bg-[var(--bg-soft)] border-y border-[var(--line)]"
      >
        <div className="container-2xl">
          <SectionHeading
            label="The pipeline"
            heading={
              <>
                From RFC to <span className="brand-pill">signed-off ADR</span>{' '}
                in seven stages.
              </>
            }
            description="Each stage is a discrete LLM call you can inspect, replay, or skip. The whole review runs in under a minute on Gemini Flash."
          />

          <motion.div
            variants={staggerContainer}
            initial={initialState}
            whileInView="visible"
            viewport={{ once: true, amount: 0.15 }}
            className="mt-14 grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
          >
            {pipelineStages.map((stage) => (
              <motion.div
                key={stage.n}
                variants={staggerItem}
                whileHover={{ y: -3, transition: { duration: 0.2 } }}
                className="card p-5 hover:bg-[var(--card-hover)] hover:border-[var(--brand)] transition-colors"
              >
                <div className="flex items-baseline justify-between">
                  <span className="font-mono text-xs font-medium text-[var(--brand)]">
                    {stage.n}
                  </span>
                  <ArrowRight className="h-3 w-3 text-[var(--muted)]" />
                </div>
                <h3 className="mt-4 font-display text-base font-medium text-[var(--ink)]">
                  {stage.title}
                </h3>
                <p className="mt-2 text-xs leading-relaxed text-[var(--muted)]">
                  {stage.description}
                </p>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </RevealSection>

      {/* ============================================
          Use cases
          ============================================ */}
      <RevealSection className="section">
        <div className="container-2xl">
          <SectionHeading
            label="Use cases"
            heading={
              <>
                The RFCs that <span className="brand-pill">need pushback</span>.
              </>
            }
            description="Anywhere you'd benefit from a disciplined panel of skeptical reviewers before you ship, Quorum gives you one in seconds — informed by your actual design doc."
          />

          <motion.div
            variants={staggerContainer}
            initial={initialState}
            whileInView="visible"
            viewport={{ once: true, amount: 0.15 }}
            className="mt-14 grid gap-4 md:grid-cols-2"
          >
            {useCases.map((uc) => {
              const Icon = uc.icon
              return (
                <motion.div
                  key={uc.title}
                  variants={staggerItem}
                  whileHover={{ y: -3, transition: { duration: 0.2 } }}
                  className="card p-6 hover:border-[var(--brand)] transition-colors"
                >
                  <div className="flex items-center gap-2 mb-3">
                    <Icon className="h-3.5 w-3.5 text-[var(--brand)]" />
                    <span className="label-mono">{uc.label}</span>
                  </div>
                  <h3 className="font-display text-xl font-medium text-[var(--ink)] tracking-tight">
                    {uc.title}
                  </h3>
                  <p className="mt-3 text-sm text-[var(--muted)] leading-relaxed">
                    {uc.body}
                  </p>
                </motion.div>
              )
            })}
          </motion.div>
        </div>
      </RevealSection>

      {/* ============================================
          Code preview — quick start
          ============================================ */}
      <RevealSection className="section bg-[var(--bg-soft)] border-y border-[var(--line)]">
        <div className="container-2xl">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <motion.div
              variants={fadeUp}
              initial={initialState}
              whileInView="visible"
              viewport={{ once: true, amount: 0.3 }}
            >
              <p className="label-mono">Quick start</p>
              <h2 className="h2 mt-4 text-[var(--ink)]">
                A few <span className="brand-pill">curl</span> calls.
              </h2>
              <p className="mt-5 text-lg text-[var(--muted)]">
                The backend exposes a clean REST API for the whole review.
                Post the decision, upload the design doc, run the panel, get
                the ADR back as Markdown.
              </p>
              <div className="mt-8 flex gap-3">
                <Link href="/workspace" className="btn btn-primary">
                  Try it now
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <Link href="/docs/api-reference" className="btn btn-ghost">
                  API reference
                  <ArrowUpRight className="h-4 w-4" />
                </Link>
              </div>
            </motion.div>
            <motion.div
              variants={fadeUp}
              initial={initialState}
              whileInView="visible"
              viewport={{ once: true, amount: 0.3 }}
              transition={{ delay: 0.1 }}
              className="code-block"
            >
              <div className="flex items-center justify-between mb-4 pb-3 border-b border-[var(--brand)]/30">
                <span className="text-xs font-mono text-[var(--brand)]">
                  Quorum REST API
                </span>
                <span className="text-xs font-mono text-[var(--muted)]">200 OK</span>
              </div>
              <pre className="text-xs whitespace-pre-wrap">
{`# 1. Open the review (defaults to the engineering RFC domain)
curl -X POST localhost:8000/api/projects \\
  -d '{
    "title": "Adopt PostgreSQL over MongoDB for orders",
    "brief": "Orders service has outgrown the sharded Mongo cluster.
      Weighing managed PostgreSQL vs. staying on Mongo with stricter
      schema enforcement. 1-quarter migration budget, 5-min downtime
      windows max, analytics expects relational joins."
  }'

# 2. Drop in the existing design doc
curl -X POST localhost:8000/api/projects/proj_X/upload \\
  -F "file=@orders-storage-rfc.pdf"

# 3. Apply the RFC ontology + build the graph
curl -X POST localhost:8000/api/projects/proj_X/graph/ontology/generate
curl -X POST localhost:8000/api/projects/proj_X/graph/build

# 4. Convene the reviewer panel + calibrate
curl -X POST localhost:8000/api/projects/proj_X/env/setup
curl -X POST localhost:8000/api/projects/proj_X/simulation/prepare

# 5. Open the deliberation
curl -X POST localhost:8000/api/projects/proj_X/simulation/activate

# 6. Run the panel
curl -X POST localhost:8000/api/projects/proj_X/simulation/start

# 7. Emit the ADR
curl -X POST localhost:8000/api/projects/proj_X/report/generate
→ { "report": { "title": "ADR — Adopt PostgreSQL ...",
               "sections": [...], "markdown": "# ADR — ..." } }`}
              </pre>
            </motion.div>
          </div>
        </div>
      </RevealSection>

      {/* ============================================
          FAQ
          ============================================ */}
      <RevealSection className="section">
        <div className="container-2xl">
          <SectionHeading
            label="FAQ"
            heading={
              <>
                Common <span className="brand-pill">questions</span>.
              </>
            }
          />

          <motion.div
            variants={staggerContainer}
            initial={initialState}
            whileInView="visible"
            viewport={{ once: true, amount: 0.1 }}
            className="mt-12 max-w-3xl space-y-3"
          >
            {faqs.map((f, i) => (
              <motion.details
                key={i}
                variants={staggerItem}
                className="group bg-[var(--card)] border border-[var(--line)] rounded-md overflow-hidden hover:border-[var(--line-strong)] transition-colors"
              >
                <summary className="cursor-pointer flex items-center gap-3 px-5 py-4 list-none">
                  <HelpCircle className="h-3.5 w-3.5 text-[var(--brand)] flex-shrink-0" />
                  <span className="text-sm font-medium text-[var(--ink)] flex-1">
                    {f.q}
                  </span>
                  <span className="text-[var(--muted)] font-mono text-sm group-open:rotate-180 transition-transform">
                    ⌄
                  </span>
                </summary>
                <div className="px-5 pb-4 pt-1 ml-7">
                  <p className="text-sm text-[var(--muted)] leading-relaxed">{f.a}</p>
                </div>
              </motion.details>
            ))}
          </motion.div>
        </div>
      </RevealSection>

      {/* ============================================
          CTA
          ============================================ */}
      <RevealSection className="section">
        <div className="container-2xl">
          <motion.div
            variants={fadeUp}
            initial={initialState}
            whileInView="visible"
            viewport={{ once: true, amount: 0.3 }}
            className="card p-12 lg:p-20 text-center bg-[var(--card)] border border-[var(--line)]"
          >
            <motion.div
              initial={reduceMotion ? { scale: 1, opacity: 1 } : { scale: 0.6, opacity: 0 }}
              whileInView={{ scale: 1, opacity: 1 }}
              viewport={{ once: true }}
              transition={{ type: 'spring', stiffness: 200, damping: 18, delay: 0.1 }}
              className="inline-flex text-[var(--brand)] mb-6"
            >
              <QuorumMark size={48} />
            </motion.div>
            <h2 className="h2 text-[var(--ink)]">
              Ready to <span className="brand-pill">convene</span> the panel?
            </h2>
            <p className="mt-5 text-lg text-[var(--muted)] max-w-xl mx-auto">
              Launch the workspace, drop in your RFC, and watch the reviewer
              panel deliberate in real time. No setup, no signup.
            </p>
            <div className="mt-8 flex flex-wrap gap-3 justify-center">
              <Link href="/workspace" className="btn btn-primary btn-lg">
                Review an RFC
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link href="/docs" className="btn btn-ghost btn-lg">
                Read the docs
              </Link>
            </div>
          </motion.div>
        </div>
      </RevealSection>

      <SiteFooter />
    </main>
  )
}

// ============================================
// Reusable: a section that fades up when it scrolls into view
// ============================================
function RevealSection({
  children,
  className = '',
  id,
}: {
  children: React.ReactNode
  className?: string
  id?: string
}) {
  const reduceMotion = useReducedMotion()
  return (
    <motion.section
      id={id}
      className={className}
      initial={reduceMotion ? 'visible' : 'hidden'}
      whileInView="visible"
      viewport={{ once: true, amount: 0.1 }}
      variants={fadeIn}
    >
      {children}
    </motion.section>
  )
}

// ============================================
// Reusable: section heading with label + h2 + description
// ============================================
function SectionHeading({
  label,
  heading,
  description,
}: {
  label: string
  heading: React.ReactNode
  description?: string
}) {
  const reduceMotion = useReducedMotion()
  return (
    <motion.div
      initial={reduceMotion ? 'visible' : 'hidden'}
      whileInView="visible"
      viewport={{ once: true, amount: 0.6 }}
      variants={staggerContainer}
      className="max-w-2xl"
    >
      <motion.p variants={staggerItem} className="label-mono">
        {label}
      </motion.p>
      <motion.h2
        variants={staggerItem}
        className="h2 mt-4 text-[var(--ink)]"
      >
        {heading}
      </motion.h2>
      {description && (
        <motion.p
          variants={staggerItem}
          className="mt-5 text-lg text-[var(--muted)]"
        >
          {description}
        </motion.p>
      )}
    </motion.div>
  )
}

// ============================================
// Hero preview component (animated)
// ============================================
function HeroPreview() {
  const reduceMotion = useReducedMotion()
  return (
    <div className="relative">
      <div className="card p-6 bg-[var(--card)] border border-[var(--line-strong)] shadow-lg">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-[var(--brand)] pulse-dot" />
            <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--muted)]">
              Reviewer panel
            </span>
          </div>
          <span className="text-[10px] font-mono text-[var(--muted)]">Round 2 / 3</span>
        </div>

        {/* Design doc pill */}
        <div className="mb-3 flex items-center gap-2 px-3 py-2 bg-[var(--bg-soft)] border border-[var(--line)] rounded-md">
          <FileText className="h-3 w-3 text-[var(--brand)] flex-shrink-0" />
          <span className="text-[11px] text-[var(--ink)] truncate flex-1">
            orders-storage-rfc.pdf
          </span>
          <span className="text-[10px] font-mono text-[var(--muted)]">8.2 KB</span>
        </div>

        <motion.div
          variants={staggerContainer}
          initial={reduceMotion ? 'visible' : 'hidden'}
          animate="visible"
          transition={{ delayChildren: 0.5 }}
          className="space-y-3"
        >
          <PreviewMessage
            agent="Reliability (SRE)"
            color="var(--brand)"
            text="Mongo sharding ops cost is the binding constraint. RDS gives us the on-call burden back."
          />
          <PreviewMessage
            agent="Cost"
            color="var(--accent-blue)"
            text="Agreed at this scale. The number bends the wrong way past 10× though — flag a 12-month revisit."
          />
          <PreviewMessage
            agent="Skeptic"
            color="var(--accent-green)"
            text="What's the migration plan for the 5-min downtime cap? Defend that explicitly before we recommend Postgres."
          />
        </motion.div>

        <div className="mt-5 pt-4 border-t border-[var(--line)] flex items-center justify-between">
          <div>
            <p className="text-[10px] font-mono uppercase text-[var(--muted)]">
              Convergence
            </p>
            <p className="text-sm font-medium text-[var(--ink)] mt-0.5">
              5/7 with 2 dissents
            </p>
          </div>
          <div className="flex -space-x-2">
            {[
              'var(--brand)',
              'var(--accent-blue)',
              'var(--accent-green)',
              'var(--accent-purple)',
            ].map((c, i) => (
              <span
                key={i}
                className="h-6 w-6 rounded-full border-2 border-[var(--card)]"
                style={{ background: c }}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Floating accent card */}
      <motion.div
        initial={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.7, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className="absolute -bottom-6 -left-6 card p-4 bg-[var(--card)] border border-[var(--line-strong)] shadow-md hidden lg:block"
      >
        <div className="flex items-center gap-2 mb-1">
          <ScrollText className="h-3 w-3 text-[var(--brand)]" />
          <p className="text-[10px] font-mono uppercase text-[var(--muted)]">ADR</p>
        </div>
        <p className="font-display text-sm font-medium text-[var(--ink)]">8 sections drafted</p>
      </motion.div>
    </div>
  )
}

function PreviewMessage({
  agent,
  color,
  text,
}: {
  agent: string
  color: string
  text: string
}) {
  return (
    <motion.div
      variants={staggerItem}
      className="flex gap-3 p-3 rounded-md bg-[var(--bg-soft)]"
    >
      <span
        className="h-7 w-7 rounded-md flex-shrink-0 mt-0.5 inline-flex items-center justify-center"
        style={{ background: color }}
      >
        <Bot className="h-3.5 w-3.5 text-white" />
      </span>
      <div>
        <p className="text-[11px] font-mono font-medium text-[var(--ink)]">{agent}</p>
        <p className="text-xs text-[var(--muted)] mt-0.5 leading-relaxed">{text}</p>
      </div>
    </motion.div>
  )
}
