/**
 * Step 4: Assemble the final .docx from a JSON payload.
 *
 * Usage:
 *   node pipeline/docx_builder.js <payload.json> <output.docx>
 *
 * Payload schema:
 * {
 *   "header": {
 *     "date": "March 26, 2026",
 *     "role": "Lab Director",
 *     "setting": "Core Lab, AMC",
 *     "location": "US"
 *   },
 *   "transcript": [
 *     { "speaker": "DeciBio Moderator", "text": "Hello..." },
 *     { "speaker": "Stakeholder", "text": "Thanks..." }
 *   ],
 *   "notes": {
 *     "Key Themes": ["bullet 1", "bullet 2"],
 *     "Notable Quotes": ["\"quote\" — Stakeholder"],
 *     "IVD Platform & Competitive Landscape": ["..."],
 *     "Workflow & Utilization Patterns": ["..."],
 *     "Reimbursement & Coding": ["..."],
 *     "Forward-Looking Signals": ["..."]
 *   }
 * }
 */

"use strict";

const fs = require("fs");
const path = require("path");

const {
  Document,
  Packer,
  Paragraph,
  TextRun,
  HeadingLevel,
  AlignmentType,
  LevelFormat,
  PageBreak,
} = require("docx");

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

const [,, payloadPath, outputPath] = process.argv;

if (!payloadPath || !outputPath) {
  console.error("Usage: node docx_builder.js <payload.json> <output.docx>");
  process.exit(1);
}

const payload = JSON.parse(fs.readFileSync(payloadPath, "utf-8"));
buildDocument(payload, outputPath);

// ---------------------------------------------------------------------------
// Build
// ---------------------------------------------------------------------------

function buildDocument(payload, outPath) {
  const { header, transcript, notes } = payload;

  const NOTES_SECTIONS = [
    "Key Themes",
    "Notable Quotes",
    "IVD Platform & Competitive Landscape",
    "Workflow & Utilization Patterns",
    "Reimbursement & Coding",
    "Forward-Looking Signals",
  ];

  // Shared paragraph spacing
  const bodySpacing = { before: 0, after: 160 };

  // ---- Header block paragraphs ----
  function headerLine(label, value) {
    return new Paragraph({
      spacing: { before: 0, after: 60 },
      children: [
        new TextRun({ text: label, bold: true, font: "Arial", size: 22 }),
        new TextRun({ text: `\t${value}`, font: "Arial", size: 22 }),
      ],
    });
  }

  const headerParagraphs = [
    headerLine("Interview Subject:", "IVD Sequencing Landscape"),
    headerLine("Interview Date:", header.date),
    headerLine(
      "Interviewee Demographics:",
      `${header.role}, ${header.setting}, ${header.location}`
    ),
    new Paragraph({ spacing: { before: 0, after: 200 }, children: [] }),
  ];

  // ---- Transcript turns ----
  const transcriptParagraphs = [];
  for (const turn of transcript) {
    transcriptParagraphs.push(
      new Paragraph({
        spacing: bodySpacing,
        children: [
          new TextRun({ text: `${turn.speaker}: `, bold: true, font: "Arial", size: 22 }),
          new TextRun({ text: turn.text, font: "Arial", size: 22 }),
        ],
      })
    );
    // Blank line between turns
    transcriptParagraphs.push(
      new Paragraph({ spacing: { before: 0, after: 80 }, children: [] })
    );
  }

  // ---- Notes section ----
  const notesParagraphs = [
    // Page break before notes
    new Paragraph({ children: [new PageBreak()] }),
    new Paragraph({
      heading: HeadingLevel.HEADING_1,
      spacing: { before: 0, after: 240 },
      children: [new TextRun({ text: "INTERVIEW NOTES", font: "Arial" })],
    }),
  ];

  for (const sectionName of NOTES_SECTIONS) {
    const bullets = notes[sectionName] || [];

    notesParagraphs.push(
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 200, after: 100 },
        children: [new TextRun({ text: sectionName, font: "Arial" })],
      })
    );

    if (bullets.length === 0) {
      notesParagraphs.push(
        new Paragraph({
          spacing: bodySpacing,
          children: [new TextRun({ text: "(No content)", font: "Arial", size: 22, italics: true })],
        })
      );
    } else {
      for (const bullet of bullets) {
        notesParagraphs.push(
          new Paragraph({
            numbering: { reference: "bullets", level: 0 },
            spacing: { before: 0, after: 80 },
            children: [new TextRun({ text: bullet, font: "Arial", size: 22 })],
          })
        );
      }
    }
  }

  // ---- Assemble document ----
  const doc = new Document({
    styles: {
      default: {
        document: { run: { font: "Arial", size: 22 } }, // 11pt default
      },
      paragraphStyles: [
        {
          id: "Heading1",
          name: "Heading 1",
          basedOn: "Normal",
          next: "Normal",
          quickFormat: true,
          run: { size: 28, bold: true, font: "Arial", color: "000000" },
          paragraph: { spacing: { before: 240, after: 240 }, outlineLevel: 0 },
        },
        {
          id: "Heading2",
          name: "Heading 2",
          basedOn: "Normal",
          next: "Normal",
          quickFormat: true,
          run: { size: 24, bold: true, font: "Arial", color: "000000" },
          paragraph: { spacing: { before: 180, after: 120 }, outlineLevel: 1 },
        },
      ],
    },
    numbering: {
      config: [
        {
          reference: "bullets",
          levels: [
            {
              level: 0,
              format: LevelFormat.BULLET,
              text: "\u2022",
              alignment: AlignmentType.LEFT,
              style: {
                paragraph: { indent: { left: 720, hanging: 360 } },
                run: { font: "Arial" },
              },
            },
          ],
        },
      ],
    },
    sections: [
      {
        properties: {
          page: {
            size: { width: 12240, height: 15840 }, // US Letter
            margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }, // 1-inch margins
          },
        },
        children: [
          ...headerParagraphs,
          ...transcriptParagraphs,
          ...notesParagraphs,
        ],
      },
    ],
  });

  Packer.toBuffer(doc).then((buffer) => {
    fs.writeFileSync(outPath, buffer);
    console.log(`Written: ${outPath}`);
  });
}
